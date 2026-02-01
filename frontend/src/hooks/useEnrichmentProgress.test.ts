import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useEnrichmentProgress } from './useEnrichmentProgress';
import {
  useEventEnrichmentWebSocket,
  type ActiveEnrichment,
  type EnrichmentHistoryEntry,
} from './useEventEnrichmentWebSocket';

// Mock the useEventEnrichmentWebSocket hook
vi.mock('./useEventEnrichmentWebSocket', () => ({
  useEventEnrichmentWebSocket: vi.fn(() => ({
    activeEnrichments: [],
    history: [],
    completedCount: 0,
    failedCount: 0,
    isConnected: false,
    getEnrichmentByBatchId: vi.fn(),
    clearHistory: vi.fn(),
  })),
}));

const mockUseEventEnrichmentWebSocket = vi.mocked(useEventEnrichmentWebSocket);

describe('useEnrichmentProgress', () => {
  const mockClearHistory = vi.fn();
  const mockGetEnrichmentByBatchId = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEventEnrichmentWebSocket.mockReturnValue({
      activeEnrichments: [],
      history: [],
      completedCount: 0,
      failedCount: 0,
      lastUpdate: null,
      isConnected: true,
      getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
      clearHistory: mockClearHistory,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('basic functionality', () => {
    it('returns empty state when no enrichments', () => {
      const { result } = renderHook(() => useEnrichmentProgress());

      expect(result.current.activeEnrichments).toEqual([]);
      expect(result.current.history).toEqual([]);
      expect(result.current.completedCount).toBe(0);
      expect(result.current.failedCount).toBe(0);
      expect(result.current.hasActiveEnrichments).toBe(false);
    });

    it('passes options to underlying hook', () => {
      const onStarted = vi.fn();
      renderHook(() =>
        useEnrichmentProgress({
          enabled: true,
          maxHistory: 100,
          onEnrichmentStarted: onStarted,
        })
      );

      expect(mockUseEventEnrichmentWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          enabled: true,
          maxHistory: 100,
          onEnrichmentStarted: onStarted,
        })
      );
    });

    it('exposes connection status', () => {
      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [],
        history: [],
        completedCount: 0,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('getProgressForBatch', () => {
    it('returns null when batch not found', () => {
      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForBatch('unknown-batch');
      expect(progress).toBeNull();
    });

    it('returns in_progress status for active enrichment', () => {
      const activeEnrichment: ActiveEnrichment = {
        batch_id: 'batch-123',
        camera_id: 'camera-1',
        detection_count: 5,
        progress: 45,
        current_step: 'Face Detection',
        total_steps: 4,
        started_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:01:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [activeEnrichment],
        history: [],
        completedCount: 0,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForBatch('batch-123');
      expect(progress).toEqual({
        status: 'in_progress',
        progress: 45,
        stage: 'Face Detection',
        totalSteps: 4,
        hasData: true,
      });
    });

    it('returns completed status for successful history entry', () => {
      const historyEntry: EnrichmentHistoryEntry = {
        batch_id: 'batch-456',
        camera_id: 'camera-1',
        status: 'full',
        enriched_count: 5,
        duration_ms: 1500,
        finished_at: '2024-01-15T10:02:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [],
        history: [historyEntry],
        completedCount: 1,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForBatch('batch-456');
      expect(progress).toEqual({
        status: 'completed',
        hasData: true,
      });
    });

    it('returns failed status for error history entry', () => {
      const historyEntry: EnrichmentHistoryEntry = {
        batch_id: 'batch-789',
        camera_id: 'camera-1',
        status: 'error',
        error: 'Model timeout',
        finished_at: '2024-01-15T10:02:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [],
        history: [historyEntry],
        completedCount: 0,
        failedCount: 1,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForBatch('batch-789');
      expect(progress).toEqual({
        status: 'failed',
        error: 'Model timeout',
        hasData: true,
      });
    });

    it('prefers active enrichment over history', () => {
      const activeEnrichment: ActiveEnrichment = {
        batch_id: 'batch-same',
        camera_id: 'camera-1',
        detection_count: 5,
        progress: 75,
        started_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:01:00Z',
      };

      const historyEntry: EnrichmentHistoryEntry = {
        batch_id: 'batch-same',
        camera_id: 'camera-1',
        status: 'full',
        finished_at: '2024-01-15T09:50:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [activeEnrichment],
        history: [historyEntry],
        completedCount: 1,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForBatch('batch-same');
      expect(progress?.status).toBe('in_progress');
      expect(progress?.progress).toBe(75);
    });
  });

  describe('getProgressForEvent', () => {
    it('returns null when event not in batch map', () => {
      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForEvent(123);
      expect(progress).toBeNull();
    });

    it('returns progress when event is mapped to batch', () => {
      const activeEnrichment: ActiveEnrichment = {
        batch_id: 'batch-for-event',
        camera_id: 'camera-1',
        detection_count: 3,
        progress: 60,
        started_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:01:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [activeEnrichment],
        history: [],
        completedCount: 0,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const eventBatchMap = new Map<number, string>();
      eventBatchMap.set(999, 'batch-for-event');

      const { result } = renderHook(() => useEnrichmentProgress({ eventBatchMap }));

      const progress = result.current.getProgressForEvent(999);
      expect(progress).toEqual({
        status: 'in_progress',
        progress: 60,
        stage: undefined,
        totalSteps: undefined,
        hasData: true,
      });
    });
  });

  describe('hasActiveEnrichments', () => {
    it('returns false when no active enrichments', () => {
      const { result } = renderHook(() => useEnrichmentProgress());
      expect(result.current.hasActiveEnrichments).toBe(false);
    });

    it('returns true when there are active enrichments', () => {
      const activeEnrichment: ActiveEnrichment = {
        batch_id: 'batch-1',
        camera_id: 'camera-1',
        detection_count: 2,
        progress: 30,
        started_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:01:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [activeEnrichment],
        history: [],
        completedCount: 0,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());
      expect(result.current.hasActiveEnrichments).toBe(true);
    });
  });

  describe('clearHistory', () => {
    it('calls clearHistory from underlying hook', () => {
      const { result } = renderHook(() => useEnrichmentProgress());

      result.current.clearHistory();
      expect(mockClearHistory).toHaveBeenCalledTimes(1);
    });
  });

  describe('multiple enrichments', () => {
    it('handles multiple active enrichments', () => {
      const active1: ActiveEnrichment = {
        batch_id: 'batch-1',
        camera_id: 'camera-1',
        detection_count: 2,
        progress: 30,
        started_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:01:00Z',
      };

      const active2: ActiveEnrichment = {
        batch_id: 'batch-2',
        camera_id: 'camera-2',
        detection_count: 4,
        progress: 80,
        current_step: 'Pose Analysis',
        started_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:01:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [active1, active2],
        history: [],
        completedCount: 0,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());

      expect(result.current.activeEnrichments).toHaveLength(2);

      const progress1 = result.current.getProgressForBatch('batch-1');
      expect(progress1?.progress).toBe(30);

      const progress2 = result.current.getProgressForBatch('batch-2');
      expect(progress2?.progress).toBe(80);
      expect(progress2?.stage).toBe('Pose Analysis');
    });

    it('keeps most recent history entry for duplicate batches', () => {
      const older: EnrichmentHistoryEntry = {
        batch_id: 'batch-dup',
        camera_id: 'camera-1',
        status: 'partial',
        finished_at: '2024-01-15T09:00:00Z',
      };

      const newer: EnrichmentHistoryEntry = {
        batch_id: 'batch-dup',
        camera_id: 'camera-1',
        status: 'full',
        finished_at: '2024-01-15T10:00:00Z',
      };

      // History is returned with newest first
      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [],
        history: [newer, older],
        completedCount: 2,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForBatch('batch-dup');
      // Should use the first entry (newer)
      expect(progress?.status).toBe('completed');
    });
  });

  describe('partial status handling', () => {
    it('treats partial status as completed', () => {
      const historyEntry: EnrichmentHistoryEntry = {
        batch_id: 'batch-partial',
        camera_id: 'camera-1',
        status: 'partial',
        enriched_count: 3,
        finished_at: '2024-01-15T10:02:00Z',
      };

      mockUseEventEnrichmentWebSocket.mockReturnValue({
        activeEnrichments: [],
        history: [historyEntry],
        completedCount: 1,
        failedCount: 0,
        lastUpdate: null,
        isConnected: true,
        getEnrichmentByBatchId: mockGetEnrichmentByBatchId,
        clearHistory: mockClearHistory,
      });

      const { result } = renderHook(() => useEnrichmentProgress());

      const progress = result.current.getProgressForBatch('batch-partial');
      expect(progress?.status).toBe('completed');
    });
  });
});
