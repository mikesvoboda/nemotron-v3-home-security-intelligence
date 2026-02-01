/**
 * Tests for useWorkerStatusWebSocket hook (NEM-3127)
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useWorkerStatusWebSocket } from './useWorkerStatusWebSocket';

import type {
  WorkerStartedPayload,
  WorkerStoppedPayload,
  WorkerErrorPayload,
  WorkerHealthCheckFailedPayload,
  WorkerRestartingPayload,
  WorkerRecoveredPayload,
} from '../types/websocket-events';

// Store the message handler for simulating events
let capturedMessageHandler: ((data: unknown) => void) | null = null;

const mockWsReturn = {
  isConnected: true,
  lastMessage: null,
  send: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  hasExhaustedRetries: false,
  reconnectCount: 0,
  lastHeartbeat: null,
  connectionId: 'test-connection-id',
};

vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn((options: { onMessage?: (data: unknown) => void }) => {
    capturedMessageHandler = options.onMessage ?? null;
    return mockWsReturn;
  }),
}));

vi.mock('../services/api', () => ({
  buildWebSocketOptions: vi.fn(() => ({
    url: 'ws://localhost:8000/ws/system',
    protocols: [],
  })),
}));

vi.mock('../services/logger', () => ({
  logger: {
    debug: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

describe('useWorkerStatusWebSocket', () => {
  const simulateWorkerEvent = <T extends object>(type: string, data: T): void => {
    act(() => {
      if (capturedMessageHandler) {
        capturedMessageHandler({ type, data });
      }
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    capturedMessageHandler = null;
  });

  afterEach(() => {
    capturedMessageHandler = null;
  });

  describe('initialization', () => {
    it('should return initial state with empty workers', () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      expect(result.current.workers).toEqual({});
      expect(result.current.latestChange).toBeNull();
      expect(result.current.isConnected).toBe(true);
      expect(result.current.pipelineHealth).toBe('unknown');
      expect(result.current.hasError).toBe(false);
      expect(result.current.hasWarning).toBe(false);
      expect(result.current.runningCount).toBe(0);
      expect(result.current.totalCount).toBe(0);
    });

    it('should provide helper functions', () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      expect(typeof result.current.getWorkerStatus).toBe('function');
      expect(typeof result.current.isWorkerRunning).toBe('function');
      expect(typeof result.current.getErrorWorkers).toBe('function');
      expect(typeof result.current.getWarningWorkers).toBe('function');
      expect(typeof result.current.clearWorkers).toBe('function');
    });
  });

  describe('worker.started event', () => {
    it('should add worker with running state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };

      simulateWorkerEvent('worker.started', payload);

      await waitFor(() => {
        expect(result.current.workers['detection-worker-1']).toBeDefined();
      });

      expect(result.current.workers['detection-worker-1'].state).toBe('running');
      expect(result.current.workers['detection-worker-1'].type).toBe('detection');
      expect(result.current.pipelineHealth).toBe('healthy');
      expect(result.current.runningCount).toBe(1);
      expect(result.current.totalCount).toBe(1);
    });

    it('should call onStatusChange callback', async () => {
      const onStatusChange = vi.fn();
      renderHook(() => useWorkerStatusWebSocket({ onStatusChange }));

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };

      simulateWorkerEvent('worker.started', payload);

      await waitFor(() => {
        expect(onStatusChange).toHaveBeenCalledWith('worker.started', payload);
      });
    });

    it('should update latestChange', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };

      simulateWorkerEvent('worker.started', payload);

      await waitFor(() => {
        expect(result.current.latestChange).not.toBeNull();
      });

      expect(result.current.latestChange?.eventType).toBe('worker.started');
      expect(result.current.latestChange?.payload).toEqual(payload);
    });
  });

  describe('worker.stopped event', () => {
    it('should update worker to stopped state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      // First start the worker
      const startPayload: WorkerStartedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', startPayload);

      await waitFor(() => {
        expect(result.current.workers['analysis-worker-1']).toBeDefined();
      });

      // Then stop it
      const stopPayload: WorkerStoppedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: '2024-01-15T10:01:00Z',
        reason: 'Graceful shutdown',
      };
      simulateWorkerEvent('worker.stopped', stopPayload);

      await waitFor(() => {
        expect(result.current.workers['analysis-worker-1'].state).toBe('stopped');
      });

      expect(result.current.workers['analysis-worker-1'].lastError).toBe('Graceful shutdown');
      expect(result.current.pipelineHealth).toBe('warning');
      expect(result.current.hasWarning).toBe(true);
    });
  });

  describe('worker.error event', () => {
    it('should update worker to error state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerErrorPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'GPU memory exhausted',
        error_type: 'out_of_memory',
        timestamp: '2024-01-15T10:00:00Z',
        recoverable: true,
      };

      simulateWorkerEvent('worker.error', payload);

      await waitFor(() => {
        expect(result.current.workers['detection-worker-1']).toBeDefined();
      });

      expect(result.current.workers['detection-worker-1'].state).toBe('error');
      expect(result.current.workers['detection-worker-1'].lastError).toBe('GPU memory exhausted');
      expect(result.current.workers['detection-worker-1'].lastErrorType).toBe('out_of_memory');
      expect(result.current.workers['detection-worker-1'].recoverable).toBe(true);
      expect(result.current.pipelineHealth).toBe('error');
      expect(result.current.hasError).toBe(true);
    });
  });

  describe('worker.health_check_failed event', () => {
    it('should keep running state for first failure', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      // First start the worker
      const startPayload: WorkerStartedPayload = {
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', startPayload);

      await waitFor(() => {
        expect(result.current.workers['metrics-worker-1']).toBeDefined();
      });

      // Health check fails once
      const healthPayload: WorkerHealthCheckFailedPayload = {
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        error: 'Timeout',
        failure_count: 1,
        timestamp: '2024-01-15T10:01:00Z',
      };
      simulateWorkerEvent('worker.health_check_failed', healthPayload);

      await waitFor(() => {
        expect(result.current.workers['metrics-worker-1'].failureCount).toBe(1);
      });

      // Should still be running (not enough failures)
      expect(result.current.workers['metrics-worker-1'].state).toBe('running');
      expect(result.current.pipelineHealth).toBe('healthy');
    });

    it('should set error state after 3 failures', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerHealthCheckFailedPayload = {
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        error: 'Timeout',
        failure_count: 3,
        timestamp: '2024-01-15T10:01:00Z',
      };
      simulateWorkerEvent('worker.health_check_failed', payload);

      await waitFor(() => {
        expect(result.current.workers['metrics-worker-1']).toBeDefined();
      });

      expect(result.current.workers['metrics-worker-1'].state).toBe('error');
      expect(result.current.workers['metrics-worker-1'].failureCount).toBe(3);
      expect(result.current.pipelineHealth).toBe('error');
    });
  });

  describe('worker.restarting event', () => {
    it('should update worker to starting state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerRestartingPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        attempt: 2,
        max_attempts: 5,
        timestamp: '2024-01-15T10:00:00Z',
        reason: 'Error recovery',
      };

      simulateWorkerEvent('worker.restarting', payload);

      await waitFor(() => {
        expect(result.current.workers['detection-worker-1']).toBeDefined();
      });

      expect(result.current.workers['detection-worker-1'].state).toBe('starting');
      expect(result.current.workers['detection-worker-1'].restartAttempt).toBe(2);
      expect(result.current.workers['detection-worker-1'].maxRestartAttempts).toBe(5);
      expect(result.current.pipelineHealth).toBe('warning');
      expect(result.current.hasWarning).toBe(true);
    });
  });

  describe('worker.recovered event', () => {
    it('should clear error state and set running', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      // First create an error state
      const errorPayload: WorkerErrorPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection failed',
        timestamp: '2024-01-15T10:00:00Z',
        recoverable: true,
      };
      simulateWorkerEvent('worker.error', errorPayload);

      await waitFor(() => {
        expect(result.current.workers['detection-worker-1'].state).toBe('error');
      });

      // Then recover
      const recoveredPayload: WorkerRecoveredPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        previous_state: 'error',
        timestamp: '2024-01-15T10:01:00Z',
        recovery_duration_ms: 500,
      };
      simulateWorkerEvent('worker.recovered', recoveredPayload);

      await waitFor(() => {
        expect(result.current.workers['detection-worker-1'].state).toBe('running');
      });

      expect(result.current.workers['detection-worker-1'].lastError).toBeUndefined();
      expect(result.current.pipelineHealth).toBe('healthy');
      expect(result.current.hasError).toBe(false);
    });
  });

  describe('filtering', () => {
    it('should filter by worker name', async () => {
      const { result } = renderHook(() =>
        useWorkerStatusWebSocket({ filterWorker: 'detection-worker-1' })
      );

      // Event for the filtered worker
      const payload1: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', payload1);

      // Event for a different worker (should be ignored)
      const payload2: WorkerStartedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', payload2);

      await waitFor(() => {
        expect(result.current.workers['detection-worker-1']).toBeDefined();
      });

      expect(result.current.workers['analysis-worker-1']).toBeUndefined();
      expect(result.current.totalCount).toBe(1);
    });

    it('should filter by worker type', async () => {
      const { result } = renderHook(() =>
        useWorkerStatusWebSocket({ filterWorkerType: 'detection' })
      );

      // Event for detection worker (should be included)
      const payload1: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', payload1);

      // Event for analysis worker (should be ignored)
      const payload2: WorkerStartedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', payload2);

      await waitFor(() => {
        expect(result.current.workers['detection-worker-1']).toBeDefined();
      });

      expect(result.current.workers['analysis-worker-1']).toBeUndefined();
    });
  });

  describe('helper functions', () => {
    it('getWorkerStatus should return worker or undefined', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', payload);

      await waitFor(() => {
        expect(result.current.getWorkerStatus('detection-worker-1')).toBeDefined();
      });

      expect(result.current.getWorkerStatus('nonexistent')).toBeUndefined();
    });

    it('isWorkerRunning should check running state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', payload);

      await waitFor(() => {
        expect(result.current.isWorkerRunning('detection-worker-1')).toBe(true);
      });

      expect(result.current.isWorkerRunning('nonexistent')).toBe(false);
    });

    it('getErrorWorkers should return workers in error state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      // Start one worker
      simulateWorkerEvent('worker.started', {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      } as WorkerStartedPayload);

      // Error another worker
      simulateWorkerEvent('worker.error', {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        error: 'Failed',
        timestamp: '2024-01-15T10:00:00Z',
        recoverable: true,
      } as WorkerErrorPayload);

      await waitFor(() => {
        expect(result.current.totalCount).toBe(2);
      });

      const errorWorkers = result.current.getErrorWorkers();
      expect(errorWorkers).toHaveLength(1);
      expect(errorWorkers[0].name).toBe('analysis-worker-1');
    });

    it('getWarningWorkers should return workers in warning state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      // Start one worker
      simulateWorkerEvent('worker.started', {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      } as WorkerStartedPayload);

      // Stop another worker
      simulateWorkerEvent('worker.stopped', {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: '2024-01-15T10:00:00Z',
      } as WorkerStoppedPayload);

      await waitFor(() => {
        expect(result.current.totalCount).toBe(2);
      });

      const warningWorkers = result.current.getWarningWorkers();
      expect(warningWorkers).toHaveLength(1);
      expect(warningWorkers[0].name).toBe('analysis-worker-1');
    });

    it('clearWorkers should reset all state', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      };
      simulateWorkerEvent('worker.started', payload);

      await waitFor(() => {
        expect(result.current.totalCount).toBe(1);
      });

      act(() => {
        result.current.clearWorkers();
      });

      expect(result.current.workers).toEqual({});
      expect(result.current.latestChange).toBeNull();
      expect(result.current.totalCount).toBe(0);
      expect(result.current.pipelineHealth).toBe('unknown');
    });
  });

  describe('multiple workers', () => {
    it('should track multiple workers correctly', async () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      // Start multiple workers
      simulateWorkerEvent('worker.started', {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: '2024-01-15T10:00:00Z',
      } as WorkerStartedPayload);

      simulateWorkerEvent('worker.started', {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: '2024-01-15T10:00:01Z',
      } as WorkerStartedPayload);

      simulateWorkerEvent('worker.started', {
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        timestamp: '2024-01-15T10:00:02Z',
      } as WorkerStartedPayload);

      await waitFor(() => {
        expect(result.current.totalCount).toBe(3);
      });

      expect(result.current.runningCount).toBe(3);
      expect(result.current.pipelineHealth).toBe('healthy');

      // Stop one worker
      simulateWorkerEvent('worker.stopped', {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: '2024-01-15T10:01:00Z',
      } as WorkerStoppedPayload);

      await waitFor(() => {
        expect(result.current.runningCount).toBe(2);
      });

      expect(result.current.pipelineHealth).toBe('warning');

      // Error on another worker
      simulateWorkerEvent('worker.error', {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection lost',
        timestamp: '2024-01-15T10:02:00Z',
        recoverable: true,
      } as WorkerErrorPayload);

      await waitFor(() => {
        expect(result.current.runningCount).toBe(1);
      });

      expect(result.current.pipelineHealth).toBe('error');
      expect(result.current.hasError).toBe(true);
      expect(result.current.hasWarning).toBe(true);
    });
  });

  describe('non-worker messages', () => {
    it('should ignore heartbeat messages', () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      act(() => {
        if (capturedMessageHandler) {
          capturedMessageHandler({ type: 'ping' });
        }
      });

      expect(result.current.totalCount).toBe(0);
    });

    it('should ignore other event types', () => {
      const { result } = renderHook(() => useWorkerStatusWebSocket());

      act(() => {
        if (capturedMessageHandler) {
          capturedMessageHandler({
            type: 'service.status_changed',
            data: { service: 'rtdetr', status: 'healthy' },
          });
        }
      });

      expect(result.current.totalCount).toBe(0);
    });
  });
});
