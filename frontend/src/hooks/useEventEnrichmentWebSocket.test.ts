/**
 * Tests for useEventEnrichmentWebSocket hook
 *
 * NEM-3627: WebSocket handlers for enrichment.* events
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useEventEnrichmentWebSocket } from './useEventEnrichmentWebSocket';

import type {
  EnrichmentStartedPayload,
  EnrichmentProgressPayload,
  EnrichmentCompletedPayload,
  EnrichmentFailedPayload,
} from '../types/websocket-events';

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

describe('useEventEnrichmentWebSocket', () => {
  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should return initial state with no active enrichments', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());
      expect(result.current.activeEnrichments).toEqual([]);
      expect(result.current.completedCount).toBe(0);
      expect(result.current.failedCount).toBe(0);
      expect(result.current.isConnected).toBe(true);
      expect(result.current.lastUpdate).toBeNull();
    });

    it('should connect to WebSocket when enabled', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket({ enabled: true }));
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('enrichment.started events', () => {
    it('should handle enrichment started messages', () => {
      const onEnrichmentStarted = vi.fn();
      const { result } = renderHook(() =>
        useEventEnrichmentWebSocket({ onEnrichmentStarted })
      );

      const payload: EnrichmentStartedPayload = {
        batch_id: 'batch-123',
        camera_id: 'front_door',
        detection_count: 5,
        timestamp: '2026-01-25T10:00:00Z',
      };

      simulateMessage({
        type: 'enrichment.started',
        data: payload,
      });

      expect(result.current.activeEnrichments).toHaveLength(1);
      expect(result.current.activeEnrichments[0].batch_id).toBe('batch-123');
      expect(result.current.activeEnrichments[0].progress).toBe(0);
      expect(result.current.lastUpdate).not.toBeNull();
      expect(onEnrichmentStarted).toHaveBeenCalledWith(payload);
    });

    it('should track multiple active enrichments', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());

      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-1',
          camera_id: 'front_door',
          detection_count: 3,
          timestamp: '2026-01-25T10:00:00Z',
        },
      });

      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-2',
          camera_id: 'back_yard',
          detection_count: 7,
          timestamp: '2026-01-25T10:00:01Z',
        },
      });

      expect(result.current.activeEnrichments).toHaveLength(2);
    });
  });

  describe('enrichment.progress events', () => {
    it('should update progress for active enrichment', () => {
      const onEnrichmentProgress = vi.fn();
      const { result } = renderHook(() =>
        useEventEnrichmentWebSocket({ onEnrichmentProgress })
      );

      // Start an enrichment
      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-123',
          camera_id: 'front_door',
          detection_count: 5,
          timestamp: '2026-01-25T10:00:00Z',
        },
      });

      // Update progress
      const progressPayload: EnrichmentProgressPayload = {
        batch_id: 'batch-123',
        progress: 50,
        current_step: 'license_plate_detection',
        total_steps: 4,
      };

      simulateMessage({
        type: 'enrichment.progress',
        data: progressPayload,
      });

      expect(result.current.activeEnrichments[0].progress).toBe(50);
      expect(result.current.activeEnrichments[0].current_step).toBe('license_plate_detection');
      expect(onEnrichmentProgress).toHaveBeenCalledWith(progressPayload);
    });

    it('should ignore progress for unknown batch', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());

      simulateMessage({
        type: 'enrichment.progress',
        data: {
          batch_id: 'unknown-batch',
          progress: 50,
          current_step: 'test',
        },
      });

      expect(result.current.activeEnrichments).toHaveLength(0);
    });
  });

  describe('enrichment.completed events', () => {
    it('should remove enrichment from active and increment completed count', () => {
      const onEnrichmentCompleted = vi.fn();
      const { result } = renderHook(() =>
        useEventEnrichmentWebSocket({ onEnrichmentCompleted })
      );

      // Start an enrichment
      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-123',
          camera_id: 'front_door',
          detection_count: 5,
          timestamp: '2026-01-25T10:00:00Z',
        },
      });

      expect(result.current.activeEnrichments).toHaveLength(1);
      expect(result.current.completedCount).toBe(0);

      // Complete the enrichment
      const completedPayload: EnrichmentCompletedPayload = {
        batch_id: 'batch-123',
        status: 'full',
        enriched_count: 5,
        duration_ms: 1500,
      };

      simulateMessage({
        type: 'enrichment.completed',
        data: completedPayload,
      });

      expect(result.current.activeEnrichments).toHaveLength(0);
      expect(result.current.completedCount).toBe(1);
      expect(onEnrichmentCompleted).toHaveBeenCalledWith(completedPayload);
    });

    it('should add to history when completed', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket({ maxHistory: 10 }));

      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-123',
          camera_id: 'front_door',
          detection_count: 5,
          timestamp: '2026-01-25T10:00:00Z',
        },
      });

      simulateMessage({
        type: 'enrichment.completed',
        data: {
          batch_id: 'batch-123',
          status: 'full',
          enriched_count: 5,
        },
      });

      expect(result.current.history).toHaveLength(1);
      expect(result.current.history[0].batch_id).toBe('batch-123');
      expect(result.current.history[0].status).toBe('full');
    });
  });

  describe('enrichment.failed events', () => {
    it('should remove enrichment from active and increment failed count', () => {
      const onEnrichmentFailed = vi.fn();
      const { result } = renderHook(() =>
        useEventEnrichmentWebSocket({ onEnrichmentFailed })
      );

      // Start an enrichment
      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-123',
          camera_id: 'front_door',
          detection_count: 5,
          timestamp: '2026-01-25T10:00:00Z',
        },
      });

      expect(result.current.activeEnrichments).toHaveLength(1);
      expect(result.current.failedCount).toBe(0);

      // Fail the enrichment
      const failedPayload: EnrichmentFailedPayload = {
        batch_id: 'batch-123',
        error: 'Connection timeout',
        error_type: 'timeout',
      };

      simulateMessage({
        type: 'enrichment.failed',
        data: failedPayload,
      });

      expect(result.current.activeEnrichments).toHaveLength(0);
      expect(result.current.failedCount).toBe(1);
      expect(onEnrichmentFailed).toHaveBeenCalledWith(failedPayload);
    });
  });

  describe('getEnrichmentByBatchId', () => {
    it('should return active enrichment by batch ID', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());

      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-123',
          camera_id: 'front_door',
          detection_count: 5,
          timestamp: '2026-01-25T10:00:00Z',
        },
      });

      const enrichment = result.current.getEnrichmentByBatchId('batch-123');
      expect(enrichment).not.toBeNull();
      expect(enrichment?.batch_id).toBe('batch-123');
    });

    it('should return undefined for unknown batch', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());
      const enrichment = result.current.getEnrichmentByBatchId('unknown');
      expect(enrichment).toBeUndefined();
    });
  });

  describe('clearHistory', () => {
    it('should clear completed/failed history', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());

      // Complete an enrichment
      simulateMessage({
        type: 'enrichment.started',
        data: {
          batch_id: 'batch-123',
          camera_id: 'front_door',
          detection_count: 5,
          timestamp: '2026-01-25T10:00:00Z',
        },
      });

      simulateMessage({
        type: 'enrichment.completed',
        data: {
          batch_id: 'batch-123',
          status: 'full',
          enriched_count: 5,
        },
      });

      expect(result.current.history).toHaveLength(1);

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.history).toHaveLength(0);
    });
  });

  describe('message filtering', () => {
    it('should ignore non-enrichment messages', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());

      simulateMessage({ type: 'ping' });
      simulateMessage({ type: 'system_status', data: { health: 'healthy' } });
      simulateMessage({ type: 'event.created', data: { id: 1 } });

      expect(result.current.activeEnrichments).toHaveLength(0);
    });

    it('should ignore malformed messages', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket());

      simulateMessage(null);
      simulateMessage(undefined);
      simulateMessage({ type: 'enrichment.started' }); // missing data
      simulateMessage({ type: 'enrichment.started', data: null });

      expect(result.current.activeEnrichments).toHaveLength(0);
    });
  });

  describe('history limit', () => {
    it('should respect maxHistory limit', () => {
      const { result } = renderHook(() => useEventEnrichmentWebSocket({ maxHistory: 3 }));

      // Create and complete 5 enrichments
      for (let i = 1; i <= 5; i++) {
        simulateMessage({
          type: 'enrichment.started',
          data: {
            batch_id: `batch-${i}`,
            camera_id: 'cam',
            detection_count: 1,
            timestamp: `2026-01-25T10:00:0${i}Z`,
          },
        });

        simulateMessage({
          type: 'enrichment.completed',
          data: {
            batch_id: `batch-${i}`,
            status: 'full',
            enriched_count: 1,
          },
        });
      }

      expect(result.current.history).toHaveLength(3);
      // Newest first
      expect(result.current.history[0].batch_id).toBe('batch-5');
    });
  });
});
