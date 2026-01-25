/**
 * Tests for useJobLogsWebSocket hook (TDD RED)
 *
 * This hook provides real-time job log streaming via WebSocket.
 * NEM-2711
 */

/* eslint-disable @typescript-eslint/unbound-method */
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, Mock } from 'vitest';

import { useJobLogsWebSocket } from './useJobLogsWebSocket';
import { webSocketManager, resetSubscriberCounter } from './webSocketManager';

// Mock the webSocketManager module
vi.mock('./webSocketManager', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./webSocketManager')>();
  return {
    ...actual,
    webSocketManager: {
      subscribe: vi.fn(),
      send: vi.fn(),
      getConnectionState: vi.fn(),
      getSubscriberCount: vi.fn(),
      hasConnection: vi.fn(),
      reconnect: vi.fn(),
      clearAll: vi.fn(),
      reset: vi.fn(),
    },
  };
});

// Helper type for the mock subscribe function
type SubscribeCallback = Parameters<typeof webSocketManager.subscribe>[1];

describe('useJobLogsWebSocket', () => {
  let mockUnsubscribe: Mock;
  let lastSubscriber: SubscribeCallback | null = null;

  beforeEach(() => {
    resetSubscriberCounter();
    mockUnsubscribe = vi.fn();
    lastSubscriber = null;

    // Default mock implementations
    (webSocketManager.subscribe as Mock).mockImplementation(
      (_url: string, subscriber: SubscribeCallback) => {
        lastSubscriber = subscriber;
        // Simulate connection opening
        setTimeout(() => {
          subscriber.onOpen?.();
        }, 0);
        return mockUnsubscribe;
      }
    );

    (webSocketManager.send as Mock).mockReturnValue(true);

    (webSocketManager.getConnectionState as Mock).mockReturnValue({
      isConnected: true,
      reconnectCount: 0,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
    });

    (webSocketManager.getSubscriberCount as Mock).mockReturnValue(1);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should return initial state when disabled', () => {
      const { result } = renderHook(() =>
        useJobLogsWebSocket({ jobId: 'job-123', enabled: false })
      );

      expect(result.current.logs).toEqual([]);
      expect(result.current.status).toBe('disconnected');
      expect(result.current.isConnected).toBe(false);
      expect(result.current.reconnectCount).toBe(0);
    });

    it('should connect when enabled is true', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.stringContaining('/ws/jobs/job-123/logs'),
        expect.any(Object),
        expect.objectContaining({
          reconnect: true,
          maxReconnectAttempts: 5,
        })
      );
    });

    it('should not connect when enabled is false', () => {
      renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: false }));

      expect(webSocketManager.subscribe).not.toHaveBeenCalled();
    });

    it('should use correct WebSocket URL', async () => {
      const { result } = renderHook(() =>
        useJobLogsWebSocket({ jobId: 'test-job-456', enabled: true })
      );

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.stringMatching(/ws:\/\/.*\/ws\/jobs\/test-job-456\/logs/),
        expect.any(Object),
        expect.any(Object)
      );
    });
  });

  describe('connection status', () => {
    it('should report connected status when WebSocket opens', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      // Initially disconnected
      expect(result.current.status).toBe('disconnected');

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('should report reconnecting status when reconnecting', async () => {
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: false,
        reconnectCount: 2,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      act(() => {
        lastSubscriber?.onClose?.();
      });

      await waitFor(() => {
        expect(result.current.status).toBe('reconnecting');
      });

      expect(result.current.reconnectCount).toBe(2);
    });

    it('should report failed status when max retries exhausted', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(result.current.status).toBe('failed');
      expect(result.current.hasExhaustedRetries).toBe(true);
    });

    it('should report disconnected status when connection closes', async () => {
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: false,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      act(() => {
        lastSubscriber?.onClose?.();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(false);
      });
    });
  });

  describe('log message handling', () => {
    it('should append log entries when receiving log messages', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      const logMessage = {
        type: 'log',
        data: {
          timestamp: '2026-01-17T10:32:05Z',
          level: 'INFO',
          message: 'Processing batch 2/3',
        },
      };

      act(() => {
        lastSubscriber?.onMessage?.(logMessage);
      });

      expect(result.current.logs).toHaveLength(1);
      expect(result.current.logs[0]).toEqual({
        timestamp: '2026-01-17T10:32:05Z',
        level: 'INFO',
        message: 'Processing batch 2/3',
      });
    });

    it('should deduplicate logs based on timestamp and message', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      const logMessage = {
        type: 'log',
        data: {
          timestamp: '2026-01-17T10:32:05Z',
          level: 'INFO',
          message: 'Processing batch 2/3',
        },
      };

      // Send same message twice
      act(() => {
        lastSubscriber?.onMessage?.(logMessage);
        lastSubscriber?.onMessage?.(logMessage);
      });

      // Should only have one log entry
      expect(result.current.logs).toHaveLength(1);
    });

    it('should maintain log order by timestamp', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'log',
          data: {
            timestamp: '2026-01-17T10:32:10Z',
            level: 'INFO',
            message: 'Second log',
          },
        });
        lastSubscriber?.onMessage?.({
          type: 'log',
          data: {
            timestamp: '2026-01-17T10:32:05Z',
            level: 'INFO',
            message: 'First log',
          },
        });
      });

      expect(result.current.logs[0].message).toBe('First log');
      expect(result.current.logs[1].message).toBe('Second log');
    });

    it('should handle log messages with context data', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      const logMessage = {
        type: 'log',
        data: {
          timestamp: '2026-01-17T10:32:05Z',
          level: 'DEBUG',
          message: 'Processing events',
          context: { event_count: 100, batch_size: 50 },
        },
      };

      act(() => {
        lastSubscriber?.onMessage?.(logMessage);
      });

      expect(result.current.logs[0].context).toEqual({
        event_count: 100,
        batch_size: 50,
      });
    });

    it('should handle different log levels (DEBUG, INFO, WARNING, ERROR)', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
      levels.forEach((level, index) => {
        act(() => {
          lastSubscriber?.onMessage?.({
            type: 'log',
            data: {
              timestamp: `2026-01-17T10:32:0${index}Z`,
              level,
              message: `${level} message`,
            },
          });
        });
      });

      expect(result.current.logs).toHaveLength(4);
      expect(result.current.logs.map((log) => log.level)).toEqual(levels);
    });
  });

  describe('callback handlers', () => {
    it('should call onLog callback when receiving log message', async () => {
      const onLog = vi.fn();
      const { result } = renderHook(() =>
        useJobLogsWebSocket({ jobId: 'job-123', enabled: true, onLog })
      );

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      const logData = {
        timestamp: '2026-01-17T10:32:05Z',
        level: 'INFO',
        message: 'Test log',
      };

      act(() => {
        lastSubscriber?.onMessage?.({ type: 'log', data: logData });
      });

      expect(onLog).toHaveBeenCalledWith(logData);
    });

    it('should call onConnect callback when connected', async () => {
      const onConnect = vi.fn();
      renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true, onConnect }));

      await waitFor(() => {
        expect(onConnect).toHaveBeenCalled();
      });
    });

    it('should call onDisconnect callback when disconnected', async () => {
      const onDisconnect = vi.fn();
      const { result } = renderHook(() =>
        useJobLogsWebSocket({ jobId: 'job-123', enabled: true, onDisconnect })
      );

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(onDisconnect).toHaveBeenCalled();
    });

    it('should call onError callback when error occurs', async () => {
      const onError = vi.fn();
      renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true, onError }));

      await waitFor(() => {
        expect(lastSubscriber).not.toBeNull();
      });

      const errorEvent = new Event('error');
      act(() => {
        lastSubscriber?.onError?.(errorEvent);
      });

      expect(onError).toHaveBeenCalledWith(errorEvent);
    });
  });

  describe('cleanup and lifecycle', () => {
    it('should disconnect on unmount', async () => {
      const { result, unmount } = renderHook(() =>
        useJobLogsWebSocket({ jobId: 'job-123', enabled: true })
      );

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      unmount();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });

    it('should disconnect when enabled changes to false', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useJobLogsWebSocket({ jobId: 'job-123', enabled }),
        { initialProps: { enabled: true } }
      );

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      rerender({ enabled: false });

      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(result.current.status).toBe('disconnected');
    });

    it('should reconnect when jobId changes', async () => {
      const { result, rerender } = renderHook(
        ({ jobId }) => useJobLogsWebSocket({ jobId, enabled: true }),
        { initialProps: { jobId: 'job-123' } }
      );

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      rerender({ jobId: 'job-456' });

      // Should unsubscribe from old and subscribe to new
      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.stringContaining('/ws/jobs/job-456/logs'),
        expect.any(Object),
        expect.any(Object)
      );
    });

    it('should clear logs when clearLogs is called', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      // Add some logs
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'log',
          data: {
            timestamp: '2026-01-17T10:32:05Z',
            level: 'INFO',
            message: 'Test log',
          },
        });
      });

      expect(result.current.logs).toHaveLength(1);

      // Clear logs
      act(() => {
        result.current.clearLogs();
      });

      expect(result.current.logs).toHaveLength(0);
    });
  });

  describe('reconnection behavior', () => {
    it('should use exponential backoff for reconnection', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object),
        expect.objectContaining({
          reconnect: true,
          reconnectInterval: expect.any(Number),
          maxReconnectAttempts: 5,
        })
      );
    });

    it('should respect maxReconnectAttempts option', async () => {
      const { result } = renderHook(() =>
        useJobLogsWebSocket({
          jobId: 'job-123',
          enabled: true,
          maxReconnectAttempts: 3,
        })
      );

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object),
        expect.objectContaining({
          maxReconnectAttempts: 3,
        })
      );
    });
  });

  describe('message type filtering', () => {
    it('should ignore non-log messages', async () => {
      const { result } = renderHook(() => useJobLogsWebSocket({ jobId: 'job-123', enabled: true }));

      await waitFor(() => {
        expect(result.current.status).toBe('connected');
      });

      // Send a non-log message
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'ping',
        });
        lastSubscriber?.onMessage?.({
          type: 'other_message',
          data: { some: 'data' },
        });
      });

      expect(result.current.logs).toHaveLength(0);
    });
  });
});
