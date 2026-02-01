/**
 * Tests for usePlateReadWebSocket hook (NEM-4865)
 *
 * This hook subscribes to WebSocket plate read events and provides callbacks
 * for handling new plate detections in real-time.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';

import { usePlateReadWebSocket, plateReadsQueryKeys } from './usePlateReadWebSocket';
import { plateStatisticsQueryKeys } from './usePlateStatisticsQuery';
import * as useWebSocketModule from './useWebSocket';
import { createQueryClient } from '../services/queryClient';

import type { PlateRead } from '../types/plateRead';

// Track the captured onMessage callback
let capturedOnMessage: ((data: unknown) => void) | undefined;

// Mock toast functions
const mockToast = {
  success: vi.fn().mockReturnValue('toast-1'),
  error: vi.fn().mockReturnValue('toast-2'),
  warning: vi.fn().mockReturnValue('toast-3'),
  info: vi.fn().mockReturnValue('toast-4'),
  loading: vi.fn().mockReturnValue('toast-5'),
  dismiss: vi.fn(),
  promise: vi.fn(),
};

// Mock the useWebSocket hook
vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn(),
}));

// Mock the useToast hook
vi.mock('./useToast', () => ({
  useToast: vi.fn(() => mockToast),
}));

// Create a wrapper with QueryClient
function createWrapper(queryClient?: QueryClient) {
  const client = queryClient ?? createQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('usePlateReadWebSocket', () => {
  let mockWebSocketReturn: ReturnType<typeof useWebSocketModule.useWebSocket>;

  // Helper to create mock plate read data
  const createMockPlateRead = (overrides: Partial<PlateRead> = {}): PlateRead => ({
    id: 123,
    camera_id: 'front_gate',
    timestamp: '2026-01-31T10:00:00Z',
    plate_text: 'ABC123',
    raw_text: 'ABC-123',
    detection_confidence: 0.95,
    ocr_confidence: 0.92,
    bbox: [100, 200, 300, 400],
    image_quality_score: 0.88,
    is_enhanced: false,
    is_blurry: false,
    created_at: '2026-01-31T10:00:00Z',
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnMessage = undefined;

    // Reset toast mocks
    mockToast.success.mockClear();
    mockToast.error.mockClear();
    mockToast.warning.mockClear();
    mockToast.info.mockClear();
    mockToast.loading.mockClear();
    mockToast.dismiss.mockClear();

    mockWebSocketReturn = {
      isConnected: true,
      lastMessage: null,
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
      connectionId: 'mock-ws-001',
    };

    (useWebSocketModule.useWebSocket as Mock).mockImplementation(
      (options: useWebSocketModule.WebSocketOptions) => {
        // Capture the onMessage callback
        capturedOnMessage = options.onMessage;
        return mockWebSocketReturn;
      }
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('query keys', () => {
    it('exports plateReadsQueryKeys with correct structure', () => {
      expect(plateReadsQueryKeys).toBeDefined();
      expect(plateReadsQueryKeys.all).toEqual(['plate-reads']);
      expect(plateReadsQueryKeys.lists()).toEqual(['plate-reads', 'list']);
    });
  });

  describe('WebSocket subscription', () => {
    it('subscribes to WebSocket with correct URL', () => {
      renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          url: expect.stringContaining('ws'),
          reconnect: true,
          reconnectInterval: 1000,
          reconnectAttempts: 15,
          connectionTimeout: 10000,
          autoRespondToHeartbeat: true,
        })
      );
    });

    it('uses custom URL when provided', () => {
      const customUrl = 'ws://custom.example.com/ws/events';
      renderHook(() => usePlateReadWebSocket({ url: customUrl }), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          url: customUrl,
        })
      );
    });

    it('disables reconnect when enabled is false', () => {
      renderHook(() => usePlateReadWebSocket({ enabled: false }), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          reconnect: false,
        })
      );
    });
  });

  describe('plate_read.created event handling', () => {
    it('handles plate_read.created messages and calls callback', () => {
      const onPlateDetected = vi.fn();
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket({ onPlateDetected }), {
        wrapper: createWrapper(),
      });

      // Simulate plate_read.created message
      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(onPlateDetected).toHaveBeenCalledWith(
        expect.objectContaining({
          id: plateData.id,
          camera_id: plateData.camera_id,
          plate_text: plateData.plate_text,
        })
      );
    });

    it('updates lastPlateRead on plate_read.created', () => {
      const plateData = createMockPlateRead();

      const { result } = renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(result.current.lastPlateRead).toEqual(
        expect.objectContaining({
          id: plateData.id,
          plate_text: plateData.plate_text,
        })
      );
    });

    it('updates lastEventType on plate_read.created', () => {
      const plateData = createMockPlateRead();

      const { result } = renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(result.current.lastEventType).toBe('plate_read.created');
    });

    it('invalidates plate reads cache on plate_read.created', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket({ autoInvalidateCache: true }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: plateReadsQueryKeys.all,
      });
    });

    it('invalidates plate statistics cache on plate_read.created', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket({ autoInvalidateCache: true }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: plateStatisticsQueryKeys.all,
      });
    });
  });

  describe('toast notifications', () => {
    it('shows toast notification when showToasts is true', () => {
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket({ showToasts: true }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(mockToast.success).toHaveBeenCalledWith(
        expect.stringContaining(plateData.plate_text),
        expect.objectContaining({ duration: 4000 })
      );
    });

    it('does not show toast when showToasts is false', () => {
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket({ showToasts: false }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(mockToast.success).not.toHaveBeenCalled();
    });

    it('does not show toast by default', () => {
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(mockToast.success).not.toHaveBeenCalled();
    });
  });

  describe('cache invalidation control', () => {
    it('does not invalidate cache when autoInvalidateCache is false', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket({ autoInvalidateCache: false }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(invalidateSpy).not.toHaveBeenCalled();
    });

    it('invalidates cache by default (autoInvalidateCache true)', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const plateData = createMockPlateRead();

      renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      expect(invalidateSpy).toHaveBeenCalled();
    });
  });

  describe('stale closure prevention', () => {
    it('uses latest callback references via refs', () => {
      const firstCallback = vi.fn();
      const secondCallback = vi.fn();
      const plateData = createMockPlateRead();

      const { rerender } = renderHook(
        ({ onPlateDetected }) => usePlateReadWebSocket({ onPlateDetected }),
        {
          wrapper: createWrapper(),
          initialProps: { onPlateDetected: firstCallback },
        }
      );

      // Update the callback
      rerender({ onPlateDetected: secondCallback });

      // Trigger plate event
      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: plateData.id,
            camera_id: plateData.camera_id,
            plate_text: plateData.plate_text,
            detection_confidence: plateData.detection_confidence,
            ocr_confidence: plateData.ocr_confidence,
            timestamp: plateData.timestamp,
          },
        });
      });

      // Should call the latest callback, not the stale one
      expect(firstCallback).not.toHaveBeenCalled();
      expect(secondCallback).toHaveBeenCalled();
    });
  });

  describe('connection state management', () => {
    it('exposes isConnected state from useWebSocket', () => {
      mockWebSocketReturn.isConnected = true;

      const { result } = renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('exposes hasExhaustedRetries state', () => {
      mockWebSocketReturn.hasExhaustedRetries = true;

      const { result } = renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
    });

    it('exposes reconnectCount state', () => {
      mockWebSocketReturn.reconnectCount = 3;

      const { result } = renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.reconnectCount).toBe(3);
    });
  });

  describe('reconnection attempts tracking', () => {
    it('tracks reconnection count', () => {
      mockWebSocketReturn.reconnectCount = 5;

      const { result } = renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.reconnectCount).toBe(5);
    });

    it('indicates when max retries are exhausted', () => {
      mockWebSocketReturn.hasExhaustedRetries = true;
      mockWebSocketReturn.reconnectCount = 15;

      const { result } = renderHook(() => usePlateReadWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
    });
  });

  describe('ignoring non-plate-read messages', () => {
    it('ignores event messages (not plate_read)', () => {
      const onPlateDetected = vi.fn();

      renderHook(() => usePlateReadWebSocket({ onPlateDetected }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'event',
          data: {
            id: 1,
            event_id: 1,
            batch_id: 'batch-1',
            camera_id: 'cam-1',
            risk_score: 75,
            risk_level: 'high',
            summary: 'Test event',
            reasoning: 'Test reasoning',
          },
        });
      });

      expect(onPlateDetected).not.toHaveBeenCalled();
    });

    it('ignores ping messages', () => {
      const onPlateDetected = vi.fn();

      renderHook(() => usePlateReadWebSocket({ onPlateDetected }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'ping',
        });
      });

      expect(onPlateDetected).not.toHaveBeenCalled();
    });

    it('ignores alert messages', () => {
      const onPlateDetected = vi.fn();

      renderHook(() => usePlateReadWebSocket({ onPlateDetected }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_created',
          data: {
            id: 'alert-123',
            event_id: 1,
            rule_id: 'rule-456',
            severity: 'high',
            status: 'pending',
          },
        });
      });

      expect(onPlateDetected).not.toHaveBeenCalled();
    });
  });

  describe('enabled option behavior', () => {
    it('calls disconnect when enabled becomes false', () => {
      const { rerender } = renderHook(({ enabled }) => usePlateReadWebSocket({ enabled }), {
        wrapper: createWrapper(),
        initialProps: { enabled: true },
      });

      // Disable the hook
      rerender({ enabled: false });

      expect(mockWebSocketReturn.disconnect).toHaveBeenCalled();
    });
  });
});
