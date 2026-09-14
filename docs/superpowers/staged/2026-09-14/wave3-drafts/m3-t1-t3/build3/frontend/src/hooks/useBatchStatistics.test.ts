/**
 * Tests for useBatchStatistics hook
 *
 * The hook combines:
 * - REST API data from /api/system/pipeline (batch_aggregator status)
 * - WebSocket events from detection.batch channel for real-time updates
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useBatchStatistics } from './useBatchStatistics';
import * as detectionStream from './useDetectionStream';
import * as api from '../services/api';

import type { PipelineStatusResponse } from '../types/generated';

// Mock the api module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchPipelineStatus: vi.fn(),
  };
});

// Mock useDetectionStream hook
vi.mock('./useDetectionStream', () => ({
  useDetectionStream: vi.fn(),
}));

const mockFetchPipelineStatus = vi.mocked(api.fetchPipelineStatus);
const mockUseDetectionStream = vi.mocked(detectionStream.useDetectionStream);

// Mock pipeline status response with batch aggregator data
const mockPipelineStatus: PipelineStatusResponse = {
  timestamp: '2026-01-25T12:00:00Z',
  batch_aggregator: {
    active_batches: 2,
    batch_window_seconds: 90,
    idle_timeout_seconds: 30,
    batches: [
      {
        batch_id: 'batch-1',
        camera_id: 'front_door',
        detection_count: 5,
        started_at: 1737806400,
        age_seconds: 45.5,
        last_activity_seconds: 10.2,
      },
      {
        batch_id: 'batch-2',
        camera_id: 'backyard',
        detection_count: 3,
        started_at: 1737806380,
        age_seconds: 65.5,
        last_activity_seconds: 5.1,
      },
    ],
  },
  file_watcher: null,
  degradation: null,
};

// Mock WebSocket batch data
const mockBatches = [
  {
    batch_id: 'completed-batch-1',
    camera_id: 'front_door',
    detection_ids: [1, 2, 3, 4, 5],
    detection_count: 5,
    started_at: '2026-01-25T11:55:00Z',
    closed_at: '2026-01-25T11:56:30Z',
    close_reason: 'timeout' as const,
  },
  {
    batch_id: 'completed-batch-2',
    camera_id: 'backyard',
    detection_ids: [6, 7],
    detection_count: 2,
    started_at: '2026-01-25T11:54:00Z',
    closed_at: '2026-01-25T11:54:30Z',
    close_reason: 'idle' as const,
  },
  {
    batch_id: 'completed-batch-3',
    camera_id: 'front_door',
    detection_ids: [8, 9, 10],
    detection_count: 3,
    started_at: '2026-01-25T11:52:00Z',
    closed_at: '2026-01-25T11:53:30Z',
    close_reason: 'max_size' as const,
  },
];

// Default mock for useDetectionStream return value
const defaultDetectionStreamReturn = {
  batches: mockBatches,
  batchCount: 3,
  isConnected: true,
  detections: [],
  latestDetection: null,
  detectionCount: 0,
  latestBatch: mockBatches[0],
  clearDetections: vi.fn(),
  clearBatches: vi.fn(),
  clearAll: vi.fn(),
  getDetectionsByBatch: vi.fn(() => []),
};

describe('useBatchStatistics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Default mock implementations
    mockFetchPipelineStatus.mockResolvedValue(mockPipelineStatus);
    mockUseDetectionStream.mockReturnValue(defaultDetectionStreamReturn);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial state', () => {
    it('should start with loading state', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      // Initially loading
      expect(result.current.isLoading).toBe(true);
      expect(result.current.error).toBeNull();

      // Wait for fetch to complete
      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('should fetch pipeline status on mount', async () => {
      renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);
    });
  });

  describe('data aggregation', () => {
    it('should return active batch count from API', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.activeBatchCount).toBe(2);
    });

    it('should return active batches from API', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.activeBatches).toHaveLength(2);
      expect(result.current.activeBatches[0].batch_id).toBe('batch-1');
    });

    it('should return completed batches from WebSocket', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.completedBatches).toHaveLength(3);
      expect(result.current.totalClosedCount).toBe(3);
    });

    it('should calculate batch statistics configuration', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.batchWindowSeconds).toBe(90);
      expect(result.current.idleTimeoutSeconds).toBe(30);
    });
  });

  describe('closure reason statistics', () => {
    it('should aggregate closure reasons from completed batches', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.closureReasonStats).toEqual({
        timeout: 1,
        idle: 1,
        max_size: 1,
      });
    });

    it('should calculate closure reason percentages', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // With 3 batches, each reason has 33.33% share
      expect(result.current.closureReasonPercentages.timeout).toBeCloseTo(33.33, 1);
      expect(result.current.closureReasonPercentages.idle).toBeCloseTo(33.33, 1);
      expect(result.current.closureReasonPercentages.max_size).toBeCloseTo(33.33, 1);
    });
  });

  describe('per-camera statistics', () => {
    it('should aggregate batches by camera', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const cameraStats = result.current.perCameraStats;

      expect(cameraStats).toHaveProperty('front_door');
      expect(cameraStats).toHaveProperty('backyard');

      // front_door: 2 completed batches + 1 active
      expect(cameraStats['front_door'].completedBatchCount).toBe(2);
      expect(cameraStats['front_door'].activeBatchCount).toBe(1);

      // backyard: 1 completed batch + 1 active
      expect(cameraStats['backyard'].completedBatchCount).toBe(1);
      expect(cameraStats['backyard'].activeBatchCount).toBe(1);
    });

    it('should calculate total detections per camera', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const cameraStats = result.current.perCameraStats;

      // front_door: 5 (batch-1) + 5 (completed-batch-1) + 3 (completed-batch-3) = 13
      expect(cameraStats['front_door'].totalDetections).toBe(13);

      // backyard: 3 (batch-2) + 2 (completed-batch-2) = 5
      expect(cameraStats['backyard'].totalDetections).toBe(5);
    });
  });

  describe('average duration calculation', () => {
    it('should calculate average batch duration from completed batches', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // completed-batch-1: 90s, completed-batch-2: 30s, completed-batch-3: 90s
      // Average: (90 + 30 + 90) / 3 = 70
      expect(result.current.averageDurationSeconds).toBeCloseTo(70, 0);
    });

    it('should return 0 for average duration when no completed batches', async () => {
      mockUseDetectionStream.mockReturnValue({
        ...defaultDetectionStreamReturn,
        batches: [],
        batchCount: 0,
        latestBatch: null,
      });

      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.averageDurationSeconds).toBe(0);
    });
  });

  describe('WebSocket connection status', () => {
    it('should expose WebSocket connection status', async () => {
      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.isWebSocketConnected).toBe(true);
    });

    it('should reflect disconnected status', async () => {
      mockUseDetectionStream.mockReturnValue({
        ...defaultDetectionStreamReturn,
        isConnected: false,
      });

      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.isWebSocketConnected).toBe(false);
    });
  });

  describe('error handling', () => {
    it('should handle API errors gracefully', async () => {
      mockFetchPipelineStatus.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe('Network error');
    });

    it('should provide retry function on error', async () => {
      mockFetchPipelineStatus.mockRejectedValueOnce(new Error('Network error'));
      mockFetchPipelineStatus.mockResolvedValueOnce(mockPipelineStatus);

      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.error).toBe('Network error');

      // Retry
      await act(async () => {
        await result.current.refetch();
      });

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.error).toBeNull();
      expect(result.current.activeBatchCount).toBe(2);
    });
  });

  describe('empty state handling', () => {
    it('should handle empty batch_aggregator response', async () => {
      mockFetchPipelineStatus.mockResolvedValue({
        timestamp: '2026-01-25T12:00:00Z',
        batch_aggregator: null,
        file_watcher: null,
        degradation: null,
      });

      mockUseDetectionStream.mockReturnValue({
        ...defaultDetectionStreamReturn,
        batches: [],
        batchCount: 0,
        latestBatch: null,
      });

      const { result } = renderHook(() => useBatchStatistics({ pollingInterval: 0 }));

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(result.current.activeBatchCount).toBe(0);
      expect(result.current.activeBatches).toHaveLength(0);
      expect(result.current.completedBatches).toHaveLength(0);
      expect(result.current.totalClosedCount).toBe(0);
      expect(result.current.averageDurationSeconds).toBe(0);
    });
  });
});
