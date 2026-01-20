/**
 * Tests for useWorkerEvents hook (NEM-3127)
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useWorkerEvents } from './useWorkerEvents';
import { useWorkerStatusStore } from '../stores/worker-status-store';

import type { WebSocketEventHandlers } from './useWebSocketEvent';
import type {
  WorkerStartedPayload,
  WorkerStoppedPayload,
  WorkerErrorPayload,
  WorkerRecoveredPayload,
} from '../types/websocket-events';

// Store captured handlers from useWebSocketEvents
let capturedHandlers: WebSocketEventHandlers = {};

const mockWsReturn = {
  isConnected: true,
  reconnectCount: 0,
  hasExhaustedRetries: false,
  lastHeartbeat: null,
  reconnect: vi.fn(),
};

vi.mock('./useWebSocketEvent', () => ({
  useWebSocketEvents: vi.fn((handlers: WebSocketEventHandlers) => {
    capturedHandlers = handlers;
    return mockWsReturn;
  }),
}));

const mockSuccess = vi.fn();
const mockError = vi.fn();
const mockWarning = vi.fn();
const mockInfo = vi.fn();

vi.mock('./useToast', () => ({
  useToast: () => ({
    success: mockSuccess,
    error: mockError,
    warning: mockWarning,
    info: mockInfo,
    loading: vi.fn(),
    dismiss: vi.fn(),
    promise: vi.fn(),
  }),
}));

describe('useWorkerEvents', () => {
  const simulateEvent = <T>(eventType: string, payload: T): void => {
    act(() => {
      const handler = capturedHandlers[eventType as keyof WebSocketEventHandlers];
      if (handler && typeof handler === 'function') {
        (handler as (p: T) => void)(payload);
      }
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    capturedHandlers = {};
    // Reset the store before each test
    useWorkerStatusStore.getState().clear();
  });

  afterEach(() => {
    useWorkerStatusStore.getState().clear();
  });

  describe('initialization', () => {
    it('should return connection state', () => {
      const { result } = renderHook(() => useWorkerEvents());

      expect(result.current.isConnected).toBe(true);
      expect(result.current.reconnectCount).toBe(0);
      expect(result.current.hasExhaustedRetries).toBe(false);
    });

    it('should accept enabled option', () => {
      renderHook(() => useWorkerEvents({ enabled: false }));

      // Hook should still return values even when disabled
      // The disabled state is passed to useWebSocketEvents
    });
  });

  describe('worker.started event', () => {
    it('should update store on worker started', () => {
      renderHook(() => useWorkerEvents());

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      };

      simulateEvent('worker.started', payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1']).toBeDefined();
      expect(state.workers['detection-worker-1'].state).toBe('running');
      expect(state.pipelineHealth).toBe('healthy');
    });

    it('should not show toast on worker started (silent)', () => {
      renderHook(() => useWorkerEvents({ showToasts: true }));

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      };

      simulateEvent('worker.started', payload);

      expect(mockSuccess).not.toHaveBeenCalled();
      expect(mockInfo).not.toHaveBeenCalled();
      expect(mockWarning).not.toHaveBeenCalled();
    });

    it('should call onWorkerEvent callback', () => {
      const onWorkerEvent = vi.fn();
      renderHook(() => useWorkerEvents({ onWorkerEvent }));

      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      };

      simulateEvent('worker.started', payload);

      expect(onWorkerEvent).toHaveBeenCalledWith('worker.started', payload);
    });
  });

  describe('worker.stopped event', () => {
    it('should update store on worker stopped', () => {
      renderHook(() => useWorkerEvents());

      // First start a worker
      const startPayload: WorkerStartedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      };
      simulateEvent('worker.started', startPayload);

      // Then stop it
      const stopPayload: WorkerStoppedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
        reason: 'Graceful shutdown',
      };
      simulateEvent('worker.stopped', stopPayload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['analysis-worker-1'].state).toBe('stopped');
      expect(state.pipelineHealth).toBe('warning');
    });

    it('should show warning toast on worker stopped', () => {
      renderHook(() => useWorkerEvents({ showToasts: true }));

      const payload: WorkerStoppedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
        reason: 'Graceful shutdown',
      };

      simulateEvent('worker.stopped', payload);

      expect(mockWarning).toHaveBeenCalledWith(
        'Worker stopped: analysis-worker-1: Graceful shutdown',
        expect.any(Object)
      );
    });

    it('should not show toast when showToasts is false', () => {
      renderHook(() => useWorkerEvents({ showToasts: false }));

      const payload: WorkerStoppedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      };

      simulateEvent('worker.stopped', payload);

      expect(mockWarning).not.toHaveBeenCalled();
    });
  });

  describe('worker.error event', () => {
    it('should update store on worker error', () => {
      renderHook(() => useWorkerEvents());

      const payload: WorkerErrorPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'GPU memory exhausted',
        error_type: 'out_of_memory',
        timestamp: new Date().toISOString(),
        recoverable: true,
      };

      simulateEvent('worker.error', payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1'].state).toBe('error');
      expect(state.workers['detection-worker-1'].lastError).toBe('GPU memory exhausted');
      expect(state.pipelineHealth).toBe('error');
      expect(state.hasError).toBe(true);
    });

    it('should show error toast on worker error', () => {
      renderHook(() => useWorkerEvents({ showToasts: true }));

      const payload: WorkerErrorPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'GPU memory exhausted',
        timestamp: new Date().toISOString(),
        recoverable: true,
      };

      simulateEvent('worker.error', payload);

      expect(mockError).toHaveBeenCalledWith(
        'Worker error: detection-worker-1',
        expect.objectContaining({
          description: 'GPU memory exhausted',
          duration: 10000,
        })
      );
    });
  });

  describe('worker.recovered event', () => {
    it('should update store on worker recovered', () => {
      renderHook(() => useWorkerEvents());

      // First create an error state
      const errorPayload: WorkerErrorPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      };
      simulateEvent('worker.error', errorPayload);

      // Then recover
      const recoveredPayload: WorkerRecoveredPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        previous_state: 'error',
        timestamp: new Date().toISOString(),
        recovery_duration_ms: 500,
      };
      simulateEvent('worker.recovered', recoveredPayload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1'].state).toBe('running');
      expect(state.pipelineHealth).toBe('healthy');
      expect(state.hasError).toBe(false);
    });

    it('should show success toast on worker recovered', () => {
      renderHook(() => useWorkerEvents({ showToasts: true }));

      const payload: WorkerRecoveredPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        previous_state: 'error',
        timestamp: new Date().toISOString(),
        recovery_duration_ms: 500,
      };

      simulateEvent('worker.recovered', payload);

      expect(mockSuccess).toHaveBeenCalledWith('Worker recovered: detection-worker-1 in 500ms');
    });
  });

  describe('multiple workers', () => {
    it('should track multiple workers correctly', () => {
      renderHook(() => useWorkerEvents());

      // Start multiple workers
      simulateEvent('worker.started', {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      } as WorkerStartedPayload);

      simulateEvent('worker.started', {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      } as WorkerStartedPayload);

      simulateEvent('worker.started', {
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        timestamp: new Date().toISOString(),
      } as WorkerStartedPayload);

      let state = useWorkerStatusStore.getState();
      expect(state.totalCount).toBe(3);
      expect(state.runningCount).toBe(3);
      expect(state.pipelineHealth).toBe('healthy');

      // Stop one worker
      simulateEvent('worker.stopped', {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      } as WorkerStoppedPayload);

      state = useWorkerStatusStore.getState();
      expect(state.runningCount).toBe(2);
      expect(state.pipelineHealth).toBe('warning');

      // Error on another worker
      simulateEvent('worker.error', {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection lost',
        timestamp: new Date().toISOString(),
        recoverable: true,
      } as WorkerErrorPayload);

      state = useWorkerStatusStore.getState();
      expect(state.runningCount).toBe(1);
      expect(state.pipelineHealth).toBe('error');
      expect(state.hasError).toBe(true);
      expect(state.hasWarning).toBe(true);
    });
  });
});
