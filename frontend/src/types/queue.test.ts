/**
 * Tests for queue type utilities and helper functions.
 */

import { describe, it, expect } from 'vitest';

import {
  computeDerivedQueueState,
  computeBatchAggregatorState,
  isCriticalStatus,
  isWarningStatus,
  isHealthyStatus,
  getHealthStatusBadgeColor,
  formatWaitTime,
  formatThroughput,
} from './queue';

import type {
  QueuesStatusResponse,
  BatchAggregatorStatusResponse,
} from './queue';

describe('computeDerivedQueueState', () => {
  it('should return empty state for null input', () => {
    const result = computeDerivedQueueState(null);

    expect(result.criticalQueues).toHaveLength(0);
    expect(result.warningQueues).toHaveLength(0);
    expect(result.longestWaitTime).toBe(0);
    expect(result.longestWaitQueue).toBeNull();
    expect(result.hasCritical).toBe(false);
    expect(result.hasIssues).toBe(false);
    expect(result.totalJobs).toBe(0);
    expect(result.totalWorkers).toBe(0);
  });

  it('should identify critical queues', () => {
    const response: QueuesStatusResponse = {
      queues: [
        {
          name: 'detection',
          status: 'critical',
          depth: 100,
          running: 4,
          workers: 4,
          throughput: { jobs_per_minute: 5, avg_processing_seconds: 12 },
          oldest_job: null,
        },
        {
          name: 'analysis',
          status: 'healthy',
          depth: 5,
          running: 2,
          workers: 4,
          throughput: { jobs_per_minute: 10, avg_processing_seconds: 6 },
          oldest_job: null,
        },
      ],
      summary: {
        total_queued: 105,
        total_running: 6,
        total_workers: 8,
        overall_status: 'critical',
      },
    };

    const result = computeDerivedQueueState(response);

    expect(result.criticalQueues).toHaveLength(1);
    expect(result.criticalQueues[0].name).toBe('detection');
    expect(result.hasCritical).toBe(true);
    expect(result.hasIssues).toBe(true);
  });

  it('should identify warning queues', () => {
    const response: QueuesStatusResponse = {
      queues: [
        {
          name: 'detection',
          status: 'warning',
          depth: 50,
          running: 4,
          workers: 4,
          throughput: { jobs_per_minute: 8, avg_processing_seconds: 7.5 },
          oldest_job: null,
        },
        {
          name: 'analysis',
          status: 'healthy',
          depth: 5,
          running: 2,
          workers: 4,
          throughput: { jobs_per_minute: 10, avg_processing_seconds: 6 },
          oldest_job: null,
        },
      ],
      summary: {
        total_queued: 55,
        total_running: 6,
        total_workers: 8,
        overall_status: 'warning',
      },
    };

    const result = computeDerivedQueueState(response);

    expect(result.warningQueues).toHaveLength(1);
    expect(result.warningQueues[0].name).toBe('detection');
    expect(result.hasCritical).toBe(false);
    expect(result.hasIssues).toBe(true);
  });

  it('should compute longest wait time', () => {
    const response: QueuesStatusResponse = {
      queues: [
        {
          name: 'detection',
          status: 'healthy',
          depth: 10,
          running: 2,
          workers: 4,
          throughput: { jobs_per_minute: 10, avg_processing_seconds: 6 },
          oldest_job: { id: 'job1', queued_at: '2026-01-25T10:00:00Z', wait_seconds: 30 },
        },
        {
          name: 'analysis',
          status: 'healthy',
          depth: 5,
          running: 2,
          workers: 4,
          throughput: { jobs_per_minute: 10, avg_processing_seconds: 6 },
          oldest_job: { id: 'job2', queued_at: '2026-01-25T09:55:00Z', wait_seconds: 120 },
        },
      ],
      summary: {
        total_queued: 15,
        total_running: 4,
        total_workers: 8,
        overall_status: 'healthy',
      },
    };

    const result = computeDerivedQueueState(response);

    expect(result.longestWaitTime).toBe(120);
    expect(result.longestWaitQueue?.name).toBe('analysis');
  });

  it('should compute total jobs and workers', () => {
    const response: QueuesStatusResponse = {
      queues: [],
      summary: {
        total_queued: 50,
        total_running: 10,
        total_workers: 8,
        overall_status: 'healthy',
      },
    };

    const result = computeDerivedQueueState(response);

    expect(result.totalJobs).toBe(60); // queued + running
    expect(result.totalWorkers).toBe(8);
  });
});

describe('computeBatchAggregatorState', () => {
  it('should return default state for null input', () => {
    const result = computeBatchAggregatorState(null);

    expect(result.activeBatchCount).toBe(0);
    expect(result.batches).toHaveLength(0);
    expect(result.batchWindowSeconds).toBe(90);
    expect(result.idleTimeoutSeconds).toBe(30);
    expect(result.batchesApproachingTimeout).toHaveLength(0);
    expect(result.hasTimeoutWarning).toBe(false);
  });

  it('should return default state for undefined input', () => {
    const result = computeBatchAggregatorState(undefined);

    expect(result.activeBatchCount).toBe(0);
    expect(result.batches).toHaveLength(0);
  });

  it('should compute batch state correctly', () => {
    const batchAggregator: BatchAggregatorStatusResponse = {
      active_batches: 2,
      batch_window_seconds: 90,
      idle_timeout_seconds: 30,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 30,
          last_activity_seconds: 5,
        },
        {
          batch_id: 'batch_002',
          camera_id: 'backyard',
          detection_count: 3,
          started_at: 1000,
          age_seconds: 60,
          last_activity_seconds: 10,
        },
      ],
    };

    const result = computeBatchAggregatorState(batchAggregator);

    expect(result.activeBatchCount).toBe(2);
    expect(result.batches).toHaveLength(2);
    expect(result.batchWindowSeconds).toBe(90);
    expect(result.idleTimeoutSeconds).toBe(30);
  });

  it('should identify batches approaching timeout (>80% of window)', () => {
    const batchAggregator: BatchAggregatorStatusResponse = {
      active_batches: 3,
      batch_window_seconds: 100, // Using 100 for easy math
      idle_timeout_seconds: 30,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 50, // 50% - not approaching
          last_activity_seconds: 5,
        },
        {
          batch_id: 'batch_002',
          camera_id: 'backyard',
          detection_count: 3,
          started_at: 1000,
          age_seconds: 80, // 80% - approaching
          last_activity_seconds: 10,
        },
        {
          batch_id: 'batch_003',
          camera_id: 'garage',
          detection_count: 2,
          started_at: 1000,
          age_seconds: 95, // 95% - approaching
          last_activity_seconds: 2,
        },
      ],
    };

    const result = computeBatchAggregatorState(batchAggregator);

    expect(result.batchesApproachingTimeout).toHaveLength(2);
    expect(result.batchesApproachingTimeout[0].batch_id).toBe('batch_002');
    expect(result.batchesApproachingTimeout[1].batch_id).toBe('batch_003');
    expect(result.hasTimeoutWarning).toBe(true);
  });

  it('should have no timeout warning when all batches are healthy', () => {
    const batchAggregator: BatchAggregatorStatusResponse = {
      active_batches: 2,
      batch_window_seconds: 90,
      idle_timeout_seconds: 30,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 30, // 33%
          last_activity_seconds: 5,
        },
        {
          batch_id: 'batch_002',
          camera_id: 'backyard',
          detection_count: 3,
          started_at: 1000,
          age_seconds: 45, // 50%
          last_activity_seconds: 10,
        },
      ],
    };

    const result = computeBatchAggregatorState(batchAggregator);

    expect(result.batchesApproachingTimeout).toHaveLength(0);
    expect(result.hasTimeoutWarning).toBe(false);
  });
});

describe('status type guards', () => {
  it('isCriticalStatus should identify critical status', () => {
    expect(isCriticalStatus('critical')).toBe(true);
    expect(isCriticalStatus('warning')).toBe(false);
    expect(isCriticalStatus('healthy')).toBe(false);
  });

  it('isWarningStatus should identify warning status', () => {
    expect(isWarningStatus('warning')).toBe(true);
    expect(isWarningStatus('critical')).toBe(false);
    expect(isWarningStatus('healthy')).toBe(false);
  });

  it('isHealthyStatus should identify healthy status', () => {
    expect(isHealthyStatus('healthy')).toBe(true);
    expect(isHealthyStatus('warning')).toBe(false);
    expect(isHealthyStatus('critical')).toBe(false);
  });
});

describe('getHealthStatusBadgeColor', () => {
  it('should return green for healthy', () => {
    expect(getHealthStatusBadgeColor('healthy')).toBe('green');
  });

  it('should return yellow for warning', () => {
    expect(getHealthStatusBadgeColor('warning')).toBe('yellow');
  });

  it('should return red for critical', () => {
    expect(getHealthStatusBadgeColor('critical')).toBe('red');
  });
});

describe('formatWaitTime', () => {
  it('should format seconds', () => {
    expect(formatWaitTime(0)).toBe('0.0s');
    expect(formatWaitTime(15.5)).toBe('15.5s');
    expect(formatWaitTime(59.9)).toBe('59.9s');
  });

  it('should format minutes and seconds', () => {
    expect(formatWaitTime(60)).toBe('1m 0s');
    expect(formatWaitTime(90)).toBe('1m 30s');
    expect(formatWaitTime(150)).toBe('2m 30s');
    expect(formatWaitTime(3599)).toBe('59m 59s');
  });

  it('should format hours and minutes', () => {
    expect(formatWaitTime(3600)).toBe('1h 0m');
    expect(formatWaitTime(5400)).toBe('1h 30m');
    expect(formatWaitTime(7200)).toBe('2h 0m');
  });
});

describe('formatThroughput', () => {
  it('should format very low throughput', () => {
    expect(formatThroughput(0)).toBe('<0.1/min');
    expect(formatThroughput(0.05)).toBe('<0.1/min');
    expect(formatThroughput(0.09)).toBe('<0.1/min');
  });

  it('should format low throughput with one decimal', () => {
    expect(formatThroughput(0.1)).toBe('0.1/min');
    expect(formatThroughput(5.5)).toBe('5.5/min');
    expect(formatThroughput(9.9)).toBe('9.9/min');
  });

  it('should format higher throughput as integers', () => {
    expect(formatThroughput(10)).toBe('10/min');
    expect(formatThroughput(25.5)).toBe('26/min');
    expect(formatThroughput(100)).toBe('100/min');
  });
});
