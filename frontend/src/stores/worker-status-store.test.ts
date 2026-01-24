import { describe, it, expect, beforeEach } from 'vitest';

import {
  useWorkerStatusStore,
  selectErrorWorkers,
  selectWarningWorkers,
  selectRunningWorkers,
  selectWorkerByName,
  selectWorkersByType,
  // Memoized selectors (NEM-3428)
  selectErrorWorkersMemoized,
  selectWarningWorkersMemoized,
  selectRunningWorkersMemoized,
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
      const { handleWorkerStarted, handleWorkerHealthCheckFailed } = useWorkerStatusStore.getState();

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
      const { handleWorkerStarted, handleWorkerHealthCheckFailed } = useWorkerStatusStore.getState();

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

  describe('memoized selectors (NEM-3428)', () => {
    beforeEach(() => {
      // Reset and set up workers in various states
      useWorkerStatusStore.getState().clear();
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
        reason: 'shutdown',
        timestamp: new Date().toISOString(),
      });

      handleWorkerError({
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        error: 'Connection failed',
        error_type: 'ConnectionError',
        recoverable: true,
        timestamp: new Date().toISOString(),
      });
    });

    it('selectErrorWorkersMemoized returns cached result on repeated calls', () => {
      const state = useWorkerStatusStore.getState();
      const result1 = selectErrorWorkersMemoized(state);
      const result2 = selectErrorWorkersMemoized(state);

      expect(result1).toBe(result2); // Same reference
      expect(result1.length).toBe(1);
      expect(result1[0].name).toBe('metrics-worker-1');
    });

    it('selectWarningWorkersMemoized returns cached result on repeated calls', () => {
      const state = useWorkerStatusStore.getState();
      const result1 = selectWarningWorkersMemoized(state);
      const result2 = selectWarningWorkersMemoized(state);

      expect(result1).toBe(result2); // Same reference
      expect(result1.length).toBe(1);
      expect(result1[0].name).toBe('analysis-worker-1');
    });

    it('selectRunningWorkersMemoized returns cached result on repeated calls', () => {
      const state = useWorkerStatusStore.getState();
      const result1 = selectRunningWorkersMemoized(state);
      const result2 = selectRunningWorkersMemoized(state);

      expect(result1).toBe(result2); // Same reference
      expect(result1.length).toBe(1);
      expect(result1[0].name).toBe('detection-worker-1');
    });

    it('memoized selectors recompute when state changes', () => {
      const state1 = useWorkerStatusStore.getState();
      const result1 = selectRunningWorkersMemoized(state1);

      // Add another running worker to change the state
      useWorkerStatusStore.getState().handleWorkerStarted({
        worker_name: 'timeout-worker-1',
        worker_type: 'timeout',
        timestamp: new Date().toISOString(),
      });

      const state2 = useWorkerStatusStore.getState();
      const result2 = selectRunningWorkersMemoized(state2);

      expect(result1).not.toBe(result2); // Different reference
      expect(result2.length).toBe(2);
    });
  });
});
