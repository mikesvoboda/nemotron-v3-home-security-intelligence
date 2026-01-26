import { act } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import {
  useWorkerStatusStore,
  selectErrorWorkers,
  selectWarningWorkers,
  selectRunningWorkers,
  selectWorkerByName,
  selectWorkersByType,
  useWorkerStatusState,
  usePipelineHealth,
  useWorkerCounts,
  useWorkerStatusActions,
} from './worker-status-store';

import type {
  WorkerStartedPayload,
  WorkerStoppedPayload,
  WorkerErrorPayload,
  WorkerHealthCheckFailedPayload,
  WorkerRestartingPayload,
  WorkerRecoveredPayload,
} from '../types/websocket-events';

describe('worker-status-store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useWorkerStatusStore.getState().clear();
  });

  describe('initial state', () => {
    it('has empty workers and unknown health initially', () => {
      const state = useWorkerStatusStore.getState();
      expect(state.workers).toEqual({});
      expect(state.pipelineHealth).toBe('unknown');
      expect(state.hasError).toBe(false);
      expect(state.hasWarning).toBe(false);
      expect(state.runningCount).toBe(0);
      expect(state.totalCount).toBe(0);
    });
  });

  describe('handleWorkerStarted', () => {
    it('adds a new running worker', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      const payload: WorkerStartedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      };

      handleWorkerStarted(payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1']).toBeDefined();
      expect(state.workers['detection-worker-1'].state).toBe('running');
      expect(state.workers['detection-worker-1'].type).toBe('detection');
      expect(state.pipelineHealth).toBe('healthy');
      expect(state.runningCount).toBe(1);
      expect(state.totalCount).toBe(1);
    });

    it('clears error state when worker starts', () => {
      const { handleWorkerError, handleWorkerStarted } = useWorkerStatusStore.getState();

      // First create an error state
      handleWorkerError({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      // Verify error state
      let state = useWorkerStatusStore.getState();
      expect(state.hasError).toBe(true);

      // Start the worker again
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      // Verify error cleared
      state = useWorkerStatusStore.getState();
      expect(state.hasError).toBe(false);
      expect(state.workers['detection-worker-1'].state).toBe('running');
      expect(state.workers['detection-worker-1'].lastError).toBeUndefined();
    });
  });

  describe('handleWorkerStopped', () => {
    it('updates worker state to stopped', () => {
      const { handleWorkerStarted, handleWorkerStopped } = useWorkerStatusStore.getState();

      // First start a worker
      handleWorkerStarted({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });

      // Stop it
      const payload: WorkerStoppedPayload = {
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
        reason: 'Graceful shutdown',
        items_processed: 100,
      };

      handleWorkerStopped(payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['analysis-worker-1'].state).toBe('stopped');
      expect(state.workers['analysis-worker-1'].lastError).toBe('Graceful shutdown');
      expect(state.pipelineHealth).toBe('warning');
      expect(state.hasWarning).toBe(true);
    });
  });

  describe('handleWorkerError', () => {
    it('updates worker state to error', () => {
      const { handleWorkerStarted, handleWorkerError } = useWorkerStatusStore.getState();

      // First start a worker
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      // Trigger an error
      const payload: WorkerErrorPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'GPU memory exhausted',
        error_type: 'out_of_memory',
        timestamp: new Date().toISOString(),
        recoverable: true,
      };

      handleWorkerError(payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1'].state).toBe('error');
      expect(state.workers['detection-worker-1'].lastError).toBe('GPU memory exhausted');
      expect(state.workers['detection-worker-1'].lastErrorType).toBe('out_of_memory');
      expect(state.workers['detection-worker-1'].recoverable).toBe(true);
      expect(state.pipelineHealth).toBe('error');
      expect(state.hasError).toBe(true);
    });

    it('creates new worker entry if not exists', () => {
      const { handleWorkerError } = useWorkerStatusStore.getState();

      handleWorkerError({
        worker_name: 'new-worker',
        worker_type: 'metrics',
        error: 'Startup failed',
        timestamp: new Date().toISOString(),
        recoverable: false,
      });

      const state = useWorkerStatusStore.getState();
      expect(state.workers['new-worker']).toBeDefined();
      expect(state.workers['new-worker'].state).toBe('error');
    });
  });

  describe('handleWorkerHealthCheckFailed', () => {
    it('keeps running state with low failure count', () => {
      const { handleWorkerStarted, handleWorkerHealthCheckFailed } =
        useWorkerStatusStore.getState();

      // Start a worker
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      // Fail health check (under threshold)
      const payload: WorkerHealthCheckFailedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Health check timeout',
        failure_count: 2,
        timestamp: new Date().toISOString(),
      };

      handleWorkerHealthCheckFailed(payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1'].state).toBe('running');
      expect(state.workers['detection-worker-1'].failureCount).toBe(2);
      expect(state.pipelineHealth).toBe('healthy');
    });

    it('changes to error state with high failure count', () => {
      const { handleWorkerStarted, handleWorkerHealthCheckFailed } =
        useWorkerStatusStore.getState();

      // Start a worker
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      // Fail health check (at threshold)
      const payload: WorkerHealthCheckFailedPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Health check timeout',
        failure_count: 3,
        timestamp: new Date().toISOString(),
      };

      handleWorkerHealthCheckFailed(payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1'].state).toBe('error');
      expect(state.workers['detection-worker-1'].failureCount).toBe(3);
      expect(state.pipelineHealth).toBe('error');
    });
  });

  describe('handleWorkerRestarting', () => {
    it('updates worker state to starting', () => {
      const { handleWorkerError, handleWorkerRestarting } = useWorkerStatusStore.getState();

      // First create an error state
      handleWorkerError({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      // Restart the worker
      const payload: WorkerRestartingPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        attempt: 1,
        max_attempts: 3,
        timestamp: new Date().toISOString(),
        reason: 'Auto-recovery',
      };

      handleWorkerRestarting(payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1'].state).toBe('starting');
      expect(state.workers['detection-worker-1'].restartAttempt).toBe(1);
      expect(state.workers['detection-worker-1'].maxRestartAttempts).toBe(3);
      expect(state.pipelineHealth).toBe('warning');
      expect(state.hasWarning).toBe(true);
    });
  });

  describe('handleWorkerRecovered', () => {
    it('updates worker state to running and clears error info', () => {
      const { handleWorkerError, handleWorkerRecovered } = useWorkerStatusStore.getState();

      // First create an error state
      handleWorkerError({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      // Recover the worker
      const payload: WorkerRecoveredPayload = {
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        previous_state: 'error',
        timestamp: new Date().toISOString(),
        recovery_duration_ms: 500,
      };

      handleWorkerRecovered(payload);

      const state = useWorkerStatusStore.getState();
      expect(state.workers['detection-worker-1'].state).toBe('running');
      expect(state.workers['detection-worker-1'].lastError).toBeUndefined();
      expect(state.workers['detection-worker-1'].lastErrorType).toBeUndefined();
      expect(state.workers['detection-worker-1'].failureCount).toBeUndefined();
      expect(state.pipelineHealth).toBe('healthy');
      expect(state.hasError).toBe(false);
    });
  });

  describe('clear', () => {
    it('resets all state to initial values', () => {
      const { handleWorkerStarted, handleWorkerError, clear } = useWorkerStatusStore.getState();

      // Add some workers
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerError({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        error: 'Failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      // Verify state was set
      let state = useWorkerStatusStore.getState();
      expect(Object.keys(state.workers).length).toBe(2);

      // Clear
      clear();

      // Verify reset
      state = useWorkerStatusStore.getState();
      expect(state.workers).toEqual({});
      expect(state.pipelineHealth).toBe('unknown');
      expect(state.hasError).toBe(false);
      expect(state.hasWarning).toBe(false);
      expect(state.runningCount).toBe(0);
      expect(state.totalCount).toBe(0);
    });
  });

  describe('derived state calculations', () => {
    it('calculates healthy status when all workers are running', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();

      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStarted({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });

      const state = useWorkerStatusStore.getState();
      expect(state.pipelineHealth).toBe('healthy');
      expect(state.runningCount).toBe(2);
      expect(state.totalCount).toBe(2);
      expect(state.hasError).toBe(false);
      expect(state.hasWarning).toBe(false);
    });

    it('calculates warning status when some workers are stopped', () => {
      const { handleWorkerStarted, handleWorkerStopped } = useWorkerStatusStore.getState();

      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStarted({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStopped({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });

      const state = useWorkerStatusStore.getState();
      expect(state.pipelineHealth).toBe('warning');
      expect(state.runningCount).toBe(1);
      expect(state.totalCount).toBe(2);
      expect(state.hasWarning).toBe(true);
    });

    it('calculates error status when any worker has error', () => {
      const { handleWorkerStarted, handleWorkerError } = useWorkerStatusStore.getState();

      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerError({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        error: 'Failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      const state = useWorkerStatusStore.getState();
      expect(state.pipelineHealth).toBe('error');
      expect(state.runningCount).toBe(1);
      expect(state.totalCount).toBe(2);
      expect(state.hasError).toBe(true);
    });
  });

  describe('selectors', () => {
    beforeEach(() => {
      const { handleWorkerStarted, handleWorkerStopped, handleWorkerError } =
        useWorkerStatusStore.getState();

      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStopped({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });
      handleWorkerError({
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        error: 'Failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });
    });

    it('selectErrorWorkers returns workers with error state', () => {
      const state = useWorkerStatusStore.getState();
      const errorWorkers = selectErrorWorkers(state);

      expect(errorWorkers.length).toBe(1);
      expect(errorWorkers[0].name).toBe('metrics-worker-1');
    });

    it('selectWarningWorkers returns workers in warning states', () => {
      const state = useWorkerStatusStore.getState();
      const warningWorkers = selectWarningWorkers(state);

      expect(warningWorkers.length).toBe(1);
      expect(warningWorkers[0].name).toBe('analysis-worker-1');
    });

    it('selectRunningWorkers returns running workers', () => {
      const state = useWorkerStatusStore.getState();
      const runningWorkers = selectRunningWorkers(state);

      expect(runningWorkers.length).toBe(1);
      expect(runningWorkers[0].name).toBe('detection-worker-1');
    });

    it('selectWorkerByName returns specific worker', () => {
      const state = useWorkerStatusStore.getState();
      const worker = selectWorkerByName(state, 'detection-worker-1');

      expect(worker).toBeDefined();
      expect(worker?.state).toBe('running');
    });

    it('selectWorkerByName returns undefined for unknown worker', () => {
      const state = useWorkerStatusStore.getState();
      const worker = selectWorkerByName(state, 'unknown-worker');

      expect(worker).toBeUndefined();
    });

    it('selectWorkersByType returns workers of specific type', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-2',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      const state = useWorkerStatusStore.getState();
      const detectionWorkers = selectWorkersByType(state, 'detection');

      expect(detectionWorkers.length).toBe(2);
      expect(detectionWorkers.every((w) => w.type === 'detection')).toBe(true);
    });
  });

  describe('subscribeWithSelector', () => {
    it('allows subscribing to pipelineHealth changes', () => {
      const callback = vi.fn();

      const unsub = (useWorkerStatusStore.subscribe as any)(
        (state: { pipelineHealth: string }) => state.pipelineHealth,
        callback
      );

      // Start a worker - health should change to 'healthy'
      act(() => {
        useWorkerStatusStore.getState().handleWorkerStarted({
          worker_name: 'worker-1',
          worker_type: 'detection',
          timestamp: new Date().toISOString(),
        });
      });

      expect(callback).toHaveBeenCalledWith('healthy', 'unknown');

      // Trigger an error - health should change to 'error'
      act(() => {
        useWorkerStatusStore.getState().handleWorkerError({
          worker_name: 'worker-1',
          worker_type: 'detection',
          error: 'Test error',
          timestamp: new Date().toISOString(),
          recoverable: true,
        });
      });

      expect(callback).toHaveBeenCalledWith('error', 'healthy');

      unsub();
    });

    it('allows subscribing to specific worker changes', () => {
      const callback = vi.fn();

      // First create the worker
      act(() => {
        useWorkerStatusStore.getState().handleWorkerStarted({
          worker_name: 'detection-worker-1',
          worker_type: 'detection',
          timestamp: new Date().toISOString(),
        });
      });

      // Subscribe to specific worker
      const unsub = (useWorkerStatusStore.subscribe as any)(
        (state: { workers: Record<string, { state: string }> }) =>
          state.workers['detection-worker-1']?.state,
        callback
      );

      // Trigger error on subscribed worker
      act(() => {
        useWorkerStatusStore.getState().handleWorkerError({
          worker_name: 'detection-worker-1',
          worker_type: 'detection',
          error: 'Connection failed',
          timestamp: new Date().toISOString(),
          recoverable: true,
        });
      });

      expect(callback).toHaveBeenCalledWith('error', 'running');

      unsub();
    });

    it('does not fire callback for unrelated worker changes', () => {
      const callback = vi.fn();

      // Create two workers
      act(() => {
        useWorkerStatusStore.getState().handleWorkerStarted({
          worker_name: 'worker-1',
          worker_type: 'detection',
          timestamp: new Date().toISOString(),
        });
        useWorkerStatusStore.getState().handleWorkerStarted({
          worker_name: 'worker-2',
          worker_type: 'analysis',
          timestamp: new Date().toISOString(),
        });
      });

      // Subscribe to worker-1's state
      const unsub = (useWorkerStatusStore.subscribe as any)(
        (state: { workers: Record<string, { state: string }> }) => state.workers['worker-1']?.state,
        callback
      );

      // Change worker-2 - callback should not fire
      act(() => {
        useWorkerStatusStore.getState().handleWorkerError({
          worker_name: 'worker-2',
          worker_type: 'analysis',
          error: 'Test error',
          timestamp: new Date().toISOString(),
          recoverable: true,
        });
      });

      expect(callback).not.toHaveBeenCalled();

      // Change worker-1 - callback should fire
      act(() => {
        useWorkerStatusStore.getState().handleWorkerError({
          worker_name: 'worker-1',
          worker_type: 'detection',
          error: 'Test error',
          timestamp: new Date().toISOString(),
          recoverable: true,
        });
      });

      expect(callback).toHaveBeenCalledTimes(1);

      unsub();
    });
  });

  describe('Immer mutations', () => {
    it('produces immutable state updates', () => {
      const initialState = useWorkerStatusStore.getState();
      const initialWorkers = initialState.workers;

      act(() => {
        useWorkerStatusStore.getState().handleWorkerStarted({
          worker_name: 'worker-1',
          worker_type: 'detection',
          timestamp: new Date().toISOString(),
        });
      });

      const newState = useWorkerStatusStore.getState();

      // States should be different references
      expect(newState).not.toBe(initialState);
      expect(newState.workers).not.toBe(initialWorkers);

      // Original object should be unchanged
      expect(Object.keys(initialWorkers)).toHaveLength(0);
      expect(Object.keys(newState.workers)).toHaveLength(1);
    });

    it('maintains immutability on worker updates', () => {
      // Create initial worker
      act(() => {
        useWorkerStatusStore.getState().handleWorkerStarted({
          worker_name: 'worker-1',
          worker_type: 'detection',
          timestamp: new Date().toISOString(),
        });
      });

      const stateAfterStart = useWorkerStatusStore.getState();
      const workerAfterStart = stateAfterStart.workers['worker-1'];

      // Update the worker
      act(() => {
        useWorkerStatusStore.getState().handleWorkerError({
          worker_name: 'worker-1',
          worker_type: 'detection',
          error: 'Test error',
          timestamp: new Date().toISOString(),
          recoverable: true,
        });
      });

      const stateAfterError = useWorkerStatusStore.getState();
      const workerAfterError = stateAfterError.workers['worker-1'];

      // Worker objects should be different references
      expect(workerAfterError).not.toBe(workerAfterStart);
      // But original should be unchanged
      expect(workerAfterStart.state).toBe('running');
      expect(workerAfterError.state).toBe('error');
    });
  });

  describe('shallow hooks (NEM-3790)', () => {
    it('useWorkerStatusState exports all state fields', () => {
      // Type check - ensure hook is exported
      expect(useWorkerStatusState).toBeDefined();
      expect(typeof useWorkerStatusState).toBe('function');
    });

    it('usePipelineHealth exports pipeline health selector', () => {
      // Type check - ensure hook is exported
      expect(usePipelineHealth).toBeDefined();
      expect(typeof usePipelineHealth).toBe('function');
    });

    it('useWorkerCounts exports count statistics', () => {
      // Type check - ensure hook is exported
      expect(useWorkerCounts).toBeDefined();
      expect(typeof useWorkerCounts).toBe('function');
    });

    it('useWorkerStatusActions exports action functions', () => {
      // Type check - ensure hook is exported
      expect(useWorkerStatusActions).toBeDefined();
      expect(typeof useWorkerStatusActions).toBe('function');
    });
  });
});
