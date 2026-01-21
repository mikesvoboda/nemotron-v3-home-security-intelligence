/**
 * Tests for useDetectionStream hook
 *
 * NEM-3169: WebSocket handlers for detection.new and detection.batch events
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useDetectionStream } from './useDetectionStream';

import type { DetectionNewData, DetectionBatchData } from '../types/websocket';

const mockOnMessage = vi.fn<(data: unknown) => void>();
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
    if (options.onMessage) {
      mockOnMessage.mockImplementation(options.onMessage);
    }
    return mockWsReturn;
  }),
}));

vi.mock('../services/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

describe('useDetectionStream', () => {
  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should return initial state with empty detections', () => {
      const { result } = renderHook(() => useDetectionStream());
      expect(result.current.detections).toEqual([]);
      expect(result.current.latestDetection).toBeNull();
      expect(result.current.batches).toEqual([]);
      expect(result.current.latestBatch).toBeNull();
      expect(result.current.isConnected).toBe(true);
      expect(result.current.detectionCount).toBe(0);
      expect(result.current.batchCount).toBe(0);
    });

    it('should connect to WebSocket when enabled', () => {
      const { result } = renderHook(() => useDetectionStream({ enabled: true }));
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('detection.new events', () => {
    it('should handle detection.new messages', () => {
      const onDetection = vi.fn();
      const { result } = renderHook(() => useDetectionStream({ onDetection }));

      const detection: DetectionNewData = {
        detection_id: 1,
        batch_id: 'batch-123',
        camera_id: 'front_door',
        label: 'person',
        confidence: 0.95,
        timestamp: '2024-01-21T10:00:00Z',
        bbox: { x: 0.1, y: 0.2, width: 0.3, height: 0.4 },
      };

      simulateMessage({
        type: 'detection.new',
        data: detection,
      });

      expect(result.current.detections).toHaveLength(1);
      expect(result.current.detections[0]).toEqual(detection);
      expect(result.current.latestDetection).toEqual(detection);
      expect(result.current.detectionCount).toBe(1);
      expect(onDetection).toHaveBeenCalledWith(detection);
    });

    it('should accumulate multiple detections', () => {
      const { result } = renderHook(() => useDetectionStream());

      const detection1: DetectionNewData = {
        detection_id: 1,
        batch_id: 'batch-123',
        camera_id: 'front_door',
        label: 'person',
        confidence: 0.95,
        timestamp: '2024-01-21T10:00:00Z',
      };

      const detection2: DetectionNewData = {
        detection_id: 2,
        batch_id: 'batch-123',
        camera_id: 'front_door',
        label: 'car',
        confidence: 0.88,
        timestamp: '2024-01-21T10:00:01Z',
      };

      simulateMessage({ type: 'detection.new', data: detection1 });
      simulateMessage({ type: 'detection.new', data: detection2 });

      expect(result.current.detections).toHaveLength(2);
      expect(result.current.latestDetection).toEqual(detection2);
      expect(result.current.detectionCount).toBe(2);
    });

    it('should respect maxDetections limit', () => {
      const { result } = renderHook(() => useDetectionStream({ maxDetections: 2 }));

      for (let i = 1; i <= 5; i++) {
        simulateMessage({
          type: 'detection.new',
          data: {
            detection_id: i,
            batch_id: `batch-${i}`,
            camera_id: 'front_door',
            label: 'person',
            confidence: 0.9,
            timestamp: `2024-01-21T10:00:0${i}Z`,
          },
        });
      }

      expect(result.current.detections).toHaveLength(2);
      // Latest detections should be first
      expect(result.current.detections[0].detection_id).toBe(5);
      expect(result.current.detections[1].detection_id).toBe(4);
    });

    it('should filter detections by camera_id when provided', () => {
      const { result } = renderHook(() =>
        useDetectionStream({ filterCameraId: 'front_door' })
      );

      simulateMessage({
        type: 'detection.new',
        data: {
          detection_id: 1,
          batch_id: 'batch-1',
          camera_id: 'front_door',
          label: 'person',
          confidence: 0.9,
          timestamp: '2024-01-21T10:00:00Z',
        },
      });

      simulateMessage({
        type: 'detection.new',
        data: {
          detection_id: 2,
          batch_id: 'batch-2',
          camera_id: 'back_yard',
          label: 'person',
          confidence: 0.9,
          timestamp: '2024-01-21T10:00:01Z',
        },
      });

      expect(result.current.detections).toHaveLength(1);
      expect(result.current.detections[0].camera_id).toBe('front_door');
    });
  });

  describe('detection.batch events', () => {
    it('should handle detection.batch messages', () => {
      const onBatch = vi.fn();
      const { result } = renderHook(() => useDetectionStream({ onBatch }));

      const batch: DetectionBatchData = {
        batch_id: 'batch-123',
        camera_id: 'front_door',
        detection_ids: [1, 2, 3],
        detection_count: 3,
        started_at: '2024-01-21T10:00:00Z',
        closed_at: '2024-01-21T10:00:30Z',
        close_reason: 'idle',
      };

      simulateMessage({
        type: 'detection.batch',
        data: batch,
      });

      expect(result.current.batches).toHaveLength(1);
      expect(result.current.batches[0]).toEqual(batch);
      expect(result.current.latestBatch).toEqual(batch);
      expect(result.current.batchCount).toBe(1);
      expect(onBatch).toHaveBeenCalledWith(batch);
    });

    it('should accumulate multiple batches', () => {
      const { result } = renderHook(() => useDetectionStream());

      const batch1: DetectionBatchData = {
        batch_id: 'batch-1',
        camera_id: 'front_door',
        detection_ids: [1, 2],
        detection_count: 2,
        started_at: '2024-01-21T10:00:00Z',
        closed_at: '2024-01-21T10:00:30Z',
      };

      const batch2: DetectionBatchData = {
        batch_id: 'batch-2',
        camera_id: 'front_door',
        detection_ids: [3, 4, 5],
        detection_count: 3,
        started_at: '2024-01-21T10:00:30Z',
        closed_at: '2024-01-21T10:01:00Z',
      };

      simulateMessage({ type: 'detection.batch', data: batch1 });
      simulateMessage({ type: 'detection.batch', data: batch2 });

      expect(result.current.batches).toHaveLength(2);
      expect(result.current.latestBatch).toEqual(batch2);
      expect(result.current.batchCount).toBe(2);
    });

    it('should respect maxBatches limit', () => {
      const { result } = renderHook(() => useDetectionStream({ maxBatches: 2 }));

      for (let i = 1; i <= 5; i++) {
        simulateMessage({
          type: 'detection.batch',
          data: {
            batch_id: `batch-${i}`,
            camera_id: 'front_door',
            detection_ids: [i],
            detection_count: 1,
            started_at: `2024-01-21T10:0${i}:00Z`,
            closed_at: `2024-01-21T10:0${i}:30Z`,
          },
        });
      }

      expect(result.current.batches).toHaveLength(2);
      // Latest batches should be first
      expect(result.current.batches[0].batch_id).toBe('batch-5');
      expect(result.current.batches[1].batch_id).toBe('batch-4');
    });

    it('should filter batches by camera_id when provided', () => {
      const { result } = renderHook(() =>
        useDetectionStream({ filterCameraId: 'front_door' })
      );

      simulateMessage({
        type: 'detection.batch',
        data: {
          batch_id: 'batch-1',
          camera_id: 'front_door',
          detection_ids: [1],
          detection_count: 1,
          started_at: '2024-01-21T10:00:00Z',
          closed_at: '2024-01-21T10:00:30Z',
        },
      });

      simulateMessage({
        type: 'detection.batch',
        data: {
          batch_id: 'batch-2',
          camera_id: 'back_yard',
          detection_ids: [2],
          detection_count: 1,
          started_at: '2024-01-21T10:00:00Z',
          closed_at: '2024-01-21T10:00:30Z',
        },
      });

      expect(result.current.batches).toHaveLength(1);
      expect(result.current.batches[0].camera_id).toBe('front_door');
    });
  });

  describe('clear functions', () => {
    it('should clear detections when clearDetections is called', () => {
      const { result } = renderHook(() => useDetectionStream());

      simulateMessage({
        type: 'detection.new',
        data: {
          detection_id: 1,
          batch_id: 'batch-1',
          camera_id: 'front_door',
          label: 'person',
          confidence: 0.9,
          timestamp: '2024-01-21T10:00:00Z',
        },
      });

      expect(result.current.detections).toHaveLength(1);

      act(() => {
        result.current.clearDetections();
      });

      expect(result.current.detections).toHaveLength(0);
      expect(result.current.latestDetection).toBeNull();
      expect(result.current.detectionCount).toBe(0);
    });

    it('should clear batches when clearBatches is called', () => {
      const { result } = renderHook(() => useDetectionStream());

      simulateMessage({
        type: 'detection.batch',
        data: {
          batch_id: 'batch-1',
          camera_id: 'front_door',
          detection_ids: [1],
          detection_count: 1,
          started_at: '2024-01-21T10:00:00Z',
          closed_at: '2024-01-21T10:00:30Z',
        },
      });

      expect(result.current.batches).toHaveLength(1);

      act(() => {
        result.current.clearBatches();
      });

      expect(result.current.batches).toHaveLength(0);
      expect(result.current.latestBatch).toBeNull();
      expect(result.current.batchCount).toBe(0);
    });

    it('should clear all when clearAll is called', () => {
      const { result } = renderHook(() => useDetectionStream());

      simulateMessage({
        type: 'detection.new',
        data: {
          detection_id: 1,
          batch_id: 'batch-1',
          camera_id: 'front_door',
          label: 'person',
          confidence: 0.9,
          timestamp: '2024-01-21T10:00:00Z',
        },
      });

      simulateMessage({
        type: 'detection.batch',
        data: {
          batch_id: 'batch-1',
          camera_id: 'front_door',
          detection_ids: [1],
          detection_count: 1,
          started_at: '2024-01-21T10:00:00Z',
          closed_at: '2024-01-21T10:00:30Z',
        },
      });

      expect(result.current.detections).toHaveLength(1);
      expect(result.current.batches).toHaveLength(1);

      act(() => {
        result.current.clearAll();
      });

      expect(result.current.detections).toHaveLength(0);
      expect(result.current.batches).toHaveLength(0);
    });
  });

  describe('getDetectionsByBatch', () => {
    it('should return detections filtered by batch_id', () => {
      const { result } = renderHook(() => useDetectionStream());

      simulateMessage({
        type: 'detection.new',
        data: {
          detection_id: 1,
          batch_id: 'batch-1',
          camera_id: 'front_door',
          label: 'person',
          confidence: 0.9,
          timestamp: '2024-01-21T10:00:00Z',
        },
      });

      simulateMessage({
        type: 'detection.new',
        data: {
          detection_id: 2,
          batch_id: 'batch-2',
          camera_id: 'front_door',
          label: 'car',
          confidence: 0.85,
          timestamp: '2024-01-21T10:00:01Z',
        },
      });

      simulateMessage({
        type: 'detection.new',
        data: {
          detection_id: 3,
          batch_id: 'batch-1',
          camera_id: 'front_door',
          label: 'dog',
          confidence: 0.88,
          timestamp: '2024-01-21T10:00:02Z',
        },
      });

      const batch1Detections = result.current.getDetectionsByBatch('batch-1');
      expect(batch1Detections).toHaveLength(2);
      expect(batch1Detections.map((d) => d.detection_id)).toEqual([3, 1]);
    });
  });

  describe('message filtering', () => {
    it('should ignore non-detection messages', () => {
      const { result } = renderHook(() => useDetectionStream());

      simulateMessage({ type: 'ping' });
      simulateMessage({ type: 'event', data: { id: 1, risk_score: 50 } });
      simulateMessage({ type: 'error', message: 'test error' });

      expect(result.current.detections).toHaveLength(0);
      expect(result.current.batches).toHaveLength(0);
    });

    it('should ignore malformed messages', () => {
      const { result } = renderHook(() => useDetectionStream());

      simulateMessage(null);
      simulateMessage(undefined);
      simulateMessage('string message');
      simulateMessage({ type: 'detection.new' }); // missing data
      simulateMessage({ type: 'detection.batch', data: {} }); // missing required fields

      expect(result.current.detections).toHaveLength(0);
      expect(result.current.batches).toHaveLength(0);
    });
  });
});
