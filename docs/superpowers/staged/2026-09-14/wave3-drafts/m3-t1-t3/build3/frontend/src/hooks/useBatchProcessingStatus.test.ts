/**
 * Tests for useBatchProcessingStatus hook (NEM-3607)
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useBatchProcessingStatus } from './useBatchProcessingStatus';

import type {
  BatchAnalysisStartedPayload,
  BatchAnalysisCompletedPayload,
  BatchAnalysisFailedPayload,
} from '../types/websocket-events';

// Store message handler from useWebSocket
type MessageHandler = (data: unknown) => void;
let capturedMessageHandler: MessageHandler | null = null;

const mockWsReturn = {
  isConnected: true,
  reconnectCount: 0,
  hasExhaustedRetries: false,
  lastHeartbeat: null,
  send: vi.fn(),
  close: vi.fn(),
};

vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn((options: { onMessage?: MessageHandler }) => {
    if (options?.onMessage) {
      capturedMessageHandler = options.onMessage;
    }
    return mockWsReturn;
  }),
}));

vi.mock('../services/api', () => ({
  buildWebSocketOptions: vi.fn(() => ({
    url: 'ws://localhost/ws/events',
    protocols: [],
  })),
}));

describe('useBatchProcessingStatus', () => {
  const simulateMessage = <T>(type: string, data: T): void => {
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

  describe('initialization', () => {
    it('should return empty initial state', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      expect(result.current.batchStatuses.size).toBe(0);
      expect(result.current.processingBatches).toEqual([]);
      expect(result.current.completedBatches).toEqual([]);
      expect(result.current.failedBatches).toEqual([]);
      expect(result.current.activeCount).toBe(0);
      expect(result.current.isConnected).toBe(true);
    });

    it('should accept enabled option', () => {
      const { result } = renderHook(() => useBatchProcessingStatus({ enabled: false }));

      // Hook should still return values even when disabled
      expect(result.current.batchStatuses.size).toBe(0);
    });

    it('should accept filterCameraId option', () => {
      const { result } = renderHook(() =>
        useBatchProcessingStatus({ filterCameraId: 'front_door' })
      );

      expect(result.current.batchStatuses.size).toBe(0);
    });
  });

  describe('batch.analysis_started event', () => {
    it('should add batch to statuses on analysis started', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      const payload: BatchAnalysisStartedPayload = {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        detection_count: 5,
        queue_position: 0,
        started_at: '2026-01-13T12:01:30.000Z',
      };

      simulateMessage('batch.analysis_started', payload);

      expect(result.current.batchStatuses.size).toBe(1);
      expect(result.current.activeCount).toBe(1);

      const status = result.current.getBatchStatus('batch_123');
      expect(status).toBeDefined();
      expect(status?.state).toBe('analyzing');
      expect(status?.cameraId).toBe('front_door');
      expect(status?.detectionCount).toBe(5);
    });

    it('should call onAnalysisStarted callback', () => {
      const onAnalysisStarted = vi.fn();
      renderHook(() => useBatchProcessingStatus({ onAnalysisStarted }));

      const payload: BatchAnalysisStartedPayload = {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        detection_count: 3,
        started_at: '2026-01-13T12:01:30.000Z',
      };

      simulateMessage('batch.analysis_started', payload);

      expect(onAnalysisStarted).toHaveBeenCalledWith(payload);
    });

    it('should filter by camera when filterCameraId is set', () => {
      const { result } = renderHook(() =>
        useBatchProcessingStatus({ filterCameraId: 'front_door' })
      );

      // This batch should be filtered out
      simulateMessage('batch.analysis_started', {
        batch_id: 'batch_123',
        camera_id: 'back_yard',
        detection_count: 3,
        started_at: '2026-01-13T12:01:30.000Z',
      });

      expect(result.current.batchStatuses.size).toBe(0);

      // This batch should be included
      simulateMessage('batch.analysis_started', {
        batch_id: 'batch_456',
        camera_id: 'front_door',
        detection_count: 3,
        started_at: '2026-01-13T12:01:30.000Z',
      });

      expect(result.current.batchStatuses.size).toBe(1);
    });
  });

  describe('batch.analysis_completed event', () => {
    it('should update batch status on analysis completed', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      // First start the batch
      simulateMessage('batch.analysis_started', {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        detection_count: 5,
        started_at: '2026-01-13T12:01:30.000Z',
      });

      expect(result.current.activeCount).toBe(1);

      // Then complete it
      const completedPayload: BatchAnalysisCompletedPayload = {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        event_id: 42,
        risk_score: 75,
        risk_level: 'high',
        duration_ms: 2500,
        completed_at: '2026-01-13T12:01:35.000Z',
      };

      simulateMessage('batch.analysis_completed', completedPayload);

      expect(result.current.activeCount).toBe(0);
      expect(result.current.completedBatches.length).toBe(1);

      const status = result.current.getBatchStatus('batch_123');
      expect(status?.state).toBe('completed');
      expect(status?.eventId).toBe(42);
      expect(status?.riskScore).toBe(75);
      expect(status?.riskLevel).toBe('high');
      expect(status?.durationMs).toBe(2500);
    });

    it('should call onAnalysisCompleted callback', () => {
      const onAnalysisCompleted = vi.fn();
      renderHook(() => useBatchProcessingStatus({ onAnalysisCompleted }));

      const payload: BatchAnalysisCompletedPayload = {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        event_id: 42,
        risk_score: 75,
        risk_level: 'high',
        duration_ms: 2500,
        completed_at: '2026-01-13T12:01:35.000Z',
      };

      simulateMessage('batch.analysis_completed', payload);

      expect(onAnalysisCompleted).toHaveBeenCalledWith(payload);
    });

    it('should handle completed event for unknown batch', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      // Complete without starting first
      simulateMessage('batch.analysis_completed', {
        batch_id: 'batch_unknown',
        camera_id: 'front_door',
        event_id: 42,
        risk_score: 75,
        risk_level: 'high',
        duration_ms: 2500,
        completed_at: '2026-01-13T12:01:35.000Z',
      });

      // Should still add the status
      expect(result.current.completedBatches.length).toBe(1);
      const status = result.current.getBatchStatus('batch_unknown');
      expect(status?.state).toBe('completed');
    });
  });

  describe('batch.analysis_failed event', () => {
    it('should update batch status on analysis failed', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      // First start the batch
      simulateMessage('batch.analysis_started', {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        detection_count: 5,
        started_at: '2026-01-13T12:01:30.000Z',
      });

      expect(result.current.activeCount).toBe(1);

      // Then fail it
      const failedPayload: BatchAnalysisFailedPayload = {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        error: 'LLM service timeout',
        error_type: 'timeout',
        retryable: true,
        failed_at: '2026-01-13T12:03:30.000Z',
      };

      simulateMessage('batch.analysis_failed', failedPayload);

      expect(result.current.activeCount).toBe(0);
      expect(result.current.failedBatches.length).toBe(1);

      const status = result.current.getBatchStatus('batch_123');
      expect(status?.state).toBe('failed');
      expect(status?.error).toBe('LLM service timeout');
      expect(status?.errorType).toBe('timeout');
      expect(status?.retryable).toBe(true);
    });

    it('should call onAnalysisFailed callback', () => {
      const onAnalysisFailed = vi.fn();
      renderHook(() => useBatchProcessingStatus({ onAnalysisFailed }));

      const payload: BatchAnalysisFailedPayload = {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        error: 'Connection error',
        error_type: 'connection',
        retryable: true,
        failed_at: '2026-01-13T12:03:30.000Z',
      };

      simulateMessage('batch.analysis_failed', payload);

      expect(onAnalysisFailed).toHaveBeenCalledWith(payload);
    });

    it('should handle non-retryable failures', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      simulateMessage('batch.analysis_failed', {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        error: 'Invalid batch format',
        error_type: 'validation',
        retryable: false,
        failed_at: '2026-01-13T12:03:30.000Z',
      });

      const status = result.current.getBatchStatus('batch_123');
      expect(status?.retryable).toBe(false);
    });
  });

  describe('history management', () => {
    it('should respect maxHistory option', () => {
      const { result } = renderHook(() => useBatchProcessingStatus({ maxHistory: 3 }));

      // Complete 5 batches
      for (let i = 1; i <= 5; i++) {
        simulateMessage('batch.analysis_completed', {
          batch_id: `batch_${i}`,
          camera_id: 'front_door',
          event_id: i,
          risk_score: 50,
          risk_level: 'medium',
          duration_ms: 1000,
          completed_at: `2026-01-13T12:0${i}:00.000Z`,
        });
      }

      // Should only keep the 3 most recent
      expect(result.current.completedBatches.length).toBeLessThanOrEqual(3);
    });

    it('should clear all history with clearHistory', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      // Add some batches
      simulateMessage('batch.analysis_started', {
        batch_id: 'batch_1',
        camera_id: 'front_door',
        detection_count: 3,
        started_at: '2026-01-13T12:01:30.000Z',
      });

      simulateMessage('batch.analysis_completed', {
        batch_id: 'batch_2',
        camera_id: 'front_door',
        event_id: 42,
        risk_score: 75,
        risk_level: 'high',
        duration_ms: 2500,
        completed_at: '2026-01-13T12:01:35.000Z',
      });

      expect(result.current.batchStatuses.size).toBe(2);

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.batchStatuses.size).toBe(0);
      expect(result.current.processingBatches).toEqual([]);
      expect(result.current.completedBatches).toEqual([]);
      expect(result.current.failedBatches).toEqual([]);
    });
  });

  describe('getBatchStatus', () => {
    it('should return undefined for unknown batch', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      const status = result.current.getBatchStatus('unknown_batch');
      expect(status).toBeUndefined();
    });

    it('should return status for known batch', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      simulateMessage('batch.analysis_started', {
        batch_id: 'batch_123',
        camera_id: 'front_door',
        detection_count: 3,
        started_at: '2026-01-13T12:01:30.000Z',
      });

      const status = result.current.getBatchStatus('batch_123');
      expect(status).toBeDefined();
      expect(status?.batchId).toBe('batch_123');
    });
  });

  describe('derived arrays', () => {
    it('should sort batches by updatedAt (most recent first)', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      // Complete batches in order
      simulateMessage('batch.analysis_completed', {
        batch_id: 'batch_1',
        camera_id: 'front_door',
        event_id: 1,
        risk_score: 50,
        risk_level: 'medium',
        duration_ms: 1000,
        completed_at: '2026-01-13T12:01:00.000Z',
      });

      simulateMessage('batch.analysis_completed', {
        batch_id: 'batch_2',
        camera_id: 'front_door',
        event_id: 2,
        risk_score: 60,
        risk_level: 'medium',
        duration_ms: 1000,
        completed_at: '2026-01-13T12:02:00.000Z',
      });

      // Most recent should be first
      expect(result.current.completedBatches[0].batchId).toBe('batch_2');
      expect(result.current.completedBatches[1].batchId).toBe('batch_1');
    });
  });

  describe('message validation', () => {
    it('should ignore messages with incorrect type format', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      // Send invalid message types
      act(() => {
        if (capturedMessageHandler) {
          capturedMessageHandler({ type: 'unknown', data: {} });
          capturedMessageHandler({ type: 'batch.unknown', data: {} });
          capturedMessageHandler({ data: {} }); // No type
          capturedMessageHandler(null);
        }
      });

      expect(result.current.batchStatuses.size).toBe(0);
    });

    it('should ignore heartbeat messages', () => {
      const { result } = renderHook(() => useBatchProcessingStatus());

      act(() => {
        if (capturedMessageHandler) {
          capturedMessageHandler({ type: 'ping' });
        }
      });

      expect(result.current.batchStatuses.size).toBe(0);
    });
  });
});
