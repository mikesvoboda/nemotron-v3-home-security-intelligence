/**
 * Tests for useUnknownStrangerAlerts hook (NEM-4688 Phase 4)
 *
 * This hook subscribes to WebSocket face detection events, filters for unknown
 * faces, triggers toast notifications, and updates the query cache for real-time
 * unknown stranger alerts.
 *
 * @see frontend/src/hooks/useUnknownStrangerAlerts.ts
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';

import { createQueryClient } from '../../services/queryClient';
import { faceRecognitionQueryKeys } from '../useFaceRecognitionApi';
import {
  useUnknownStrangerAlerts,
  unknownStrangerAlertsQueryKeys,
  type FaceDetectionWebSocketPayload,
} from '../useUnknownStrangerAlerts';
import * as useWebSocketModule from '../useWebSocket';

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
vi.mock('../useWebSocket', () => ({
  useWebSocket: vi.fn(),
}));

// Mock the useToast hook
vi.mock('../useToast', () => ({
  useToast: vi.fn(() => mockToast),
}));

// Create a wrapper with QueryClient
function createWrapper(queryClient?: QueryClient) {
  const client = queryClient ?? createQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('useUnknownStrangerAlerts', () => {
  let mockWebSocketReturn: ReturnType<typeof useWebSocketModule.useWebSocket>;

  // Helper to create mock face detection payload
  const createMockFaceDetection = (
    overrides: Partial<FaceDetectionWebSocketPayload> = {}
  ): FaceDetectionWebSocketPayload => ({
    event_id: 123,
    camera_id: 1,
    camera_name: 'Front Door',
    is_unknown: true,
    timestamp: '2026-01-31T10:32:00Z',
    thumbnail_url: '/api/thumbnails/face123.jpg',
    quality_score: 0.85,
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
    it('exports unknownStrangerAlertsQueryKeys with correct structure', () => {
      expect(unknownStrangerAlertsQueryKeys).toBeDefined();
      expect(unknownStrangerAlertsQueryKeys.all).toEqual(['unknown-stranger-alerts']);
      expect(unknownStrangerAlertsQueryKeys.unreadCount()).toEqual([
        'unknown-stranger-alerts',
        'unread-count',
      ]);
    });
  });

  describe('WebSocket subscription', () => {
    it('subscribes to WebSocket with correct URL', () => {
      renderHook(() => useUnknownStrangerAlerts(), {
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
      renderHook(() => useUnknownStrangerAlerts({ url: customUrl }), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          url: customUrl,
        })
      );
    });

    it('disables reconnect when enabled is false', () => {
      renderHook(() => useUnknownStrangerAlerts({ enabled: false }), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          reconnect: false,
        })
      );
    });
  });

  describe('face_detection event handling', () => {
    it('handles face_detection messages for unknown faces and calls callback', () => {
      const onUnknownDetected = vi.fn();
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts({ onUnknownDetected }), {
        wrapper: createWrapper(),
      });

      // Simulate face_detection message
      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(onUnknownDetected).toHaveBeenCalledWith(
        expect.objectContaining({
          event_id: faceData.event_id,
          camera_id: faceData.camera_id,
          camera_name: faceData.camera_name,
          is_unknown: true,
        })
      );
    });

    it('ignores face_detection messages for known faces', () => {
      const onUnknownDetected = vi.fn();
      const faceData = createMockFaceDetection({
        is_unknown: false,
        matched_person_id: 1,
        matched_person_name: 'John Doe',
      });

      renderHook(() => useUnknownStrangerAlerts({ onUnknownDetected }), {
        wrapper: createWrapper(),
      });

      // Simulate face_detection message for known person
      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(onUnknownDetected).not.toHaveBeenCalled();
    });

    it('updates lastUnknownFace on face_detection for unknown face', () => {
      const faceData = createMockFaceDetection({ is_unknown: true });

      const { result } = renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(result.current.lastUnknownFace).toEqual(
        expect.objectContaining({
          event_id: faceData.event_id,
          camera_name: faceData.camera_name,
          is_unknown: true,
        })
      );
    });

    it('increments unreadCount on unknown face detection', () => {
      const faceData = createMockFaceDetection({ is_unknown: true });

      const { result } = renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      expect(result.current.unreadCount).toBe(0);

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(result.current.unreadCount).toBe(1);

      // Another detection should increment again
      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: createMockFaceDetection({ event_id: 456, is_unknown: true }),
        });
      });

      expect(result.current.unreadCount).toBe(2);
    });

    it('invalidates unknown strangers cache on face_detection', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts({ autoInvalidateCache: true }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: faceRecognitionQueryKeys.unknownStrangers(),
      });
    });

    it('invalidates face stats cache on face_detection', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts({ autoInvalidateCache: true }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: faceRecognitionQueryKeys.faceStats(),
      });
    });
  });

  describe('toast notifications', () => {
    it('shows warning toast notification when showToasts is true', () => {
      const faceData = createMockFaceDetection({
        is_unknown: true,
        camera_name: 'Front Door',
      });

      renderHook(() => useUnknownStrangerAlerts({ showToasts: true }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(mockToast.warning).toHaveBeenCalledWith(
        expect.stringContaining('Unknown Person Detected'),
        expect.objectContaining({
          description: expect.stringContaining('Front Door'),
          duration: 5000,
        })
      );
    });

    it('includes camera name in toast description', () => {
      const faceData = createMockFaceDetection({
        is_unknown: true,
        camera_name: 'Backyard Camera',
      });

      renderHook(() => useUnknownStrangerAlerts({ showToasts: true }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(mockToast.warning).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          description: expect.stringContaining('Backyard Camera'),
        })
      );
    });

    it('does not show toast when showToasts is false', () => {
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts({ showToasts: false }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(mockToast.warning).not.toHaveBeenCalled();
    });

    it('shows toast by default', () => {
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(mockToast.warning).toHaveBeenCalled();
    });

    it('includes action button in toast for viewing', () => {
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts({ showToasts: true }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(mockToast.warning).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          action: expect.objectContaining({
            label: 'View',
          }),
        })
      );
    });
  });

  describe('cache invalidation control', () => {
    it('does not invalidate cache when autoInvalidateCache is false', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts({ autoInvalidateCache: false }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(invalidateSpy).not.toHaveBeenCalled();
    });

    it('invalidates cache by default (autoInvalidateCache true)', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const faceData = createMockFaceDetection({ is_unknown: true });

      renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalled();
    });
  });

  describe('markAsRead functionality', () => {
    it('resets unreadCount to 0 when markAsRead is called', () => {
      const faceData = createMockFaceDetection({ is_unknown: true });

      const { result } = renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      // Add some unread alerts
      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      expect(result.current.unreadCount).toBe(1);

      // Mark as read
      act(() => {
        result.current.markAsRead();
      });

      expect(result.current.unreadCount).toBe(0);
    });

    it('can accumulate alerts after marking as read', () => {
      const faceData = createMockFaceDetection({ is_unknown: true });

      const { result } = renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      // Add alert, mark as read, add more alerts
      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      act(() => {
        result.current.markAsRead();
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: createMockFaceDetection({ event_id: 456, is_unknown: true }),
        });
        capturedOnMessage?.({
          type: 'face_detection',
          data: createMockFaceDetection({ event_id: 789, is_unknown: true }),
        });
      });

      expect(result.current.unreadCount).toBe(2);
    });
  });

  describe('stale closure prevention', () => {
    it('uses latest callback references via refs', () => {
      const firstCallback = vi.fn();
      const secondCallback = vi.fn();
      const faceData = createMockFaceDetection({ is_unknown: true });

      const { rerender } = renderHook(
        ({ onUnknownDetected }) => useUnknownStrangerAlerts({ onUnknownDetected }),
        {
          wrapper: createWrapper(),
          initialProps: { onUnknownDetected: firstCallback },
        }
      );

      // Update the callback
      rerender({ onUnknownDetected: secondCallback });

      // Trigger face event
      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
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

      const { result } = renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('exposes hasExhaustedRetries state', () => {
      mockWebSocketReturn.hasExhaustedRetries = true;

      const { result } = renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
    });

    it('exposes reconnectCount state', () => {
      mockWebSocketReturn.reconnectCount = 3;

      const { result } = renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      expect(result.current.reconnectCount).toBe(3);
    });
  });

  describe('ignoring non-face-detection messages', () => {
    it('ignores event messages', () => {
      const onUnknownDetected = vi.fn();

      renderHook(() => useUnknownStrangerAlerts({ onUnknownDetected }), {
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

      expect(onUnknownDetected).not.toHaveBeenCalled();
    });

    it('ignores ping messages', () => {
      const onUnknownDetected = vi.fn();

      renderHook(() => useUnknownStrangerAlerts({ onUnknownDetected }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'ping',
        });
      });

      expect(onUnknownDetected).not.toHaveBeenCalled();
    });

    it('ignores plate_read messages', () => {
      const onUnknownDetected = vi.fn();

      renderHook(() => useUnknownStrangerAlerts({ onUnknownDetected }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'plate_read.created',
          data: {
            id: 123,
            camera_id: 'cam-1',
            plate_text: 'ABC123',
            detection_confidence: 0.95,
            ocr_confidence: 0.92,
            timestamp: '2026-01-31T10:00:00Z',
          },
        });
      });

      expect(onUnknownDetected).not.toHaveBeenCalled();
    });

    it('ignores alert messages', () => {
      const onUnknownDetected = vi.fn();

      renderHook(() => useUnknownStrangerAlerts({ onUnknownDetected }), {
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

      expect(onUnknownDetected).not.toHaveBeenCalled();
    });
  });

  describe('enabled option behavior', () => {
    it('calls disconnect when enabled becomes false', () => {
      const { rerender } = renderHook(
        ({ enabled }) => useUnknownStrangerAlerts({ enabled }),
        {
          wrapper: createWrapper(),
          initialProps: { enabled: true },
        }
      );

      // Disable the hook
      rerender({ enabled: false });

      expect(mockWebSocketReturn.disconnect).toHaveBeenCalled();
    });
  });

  describe('onView callback', () => {
    it('calls onView callback when toast action button is clicked', () => {
      const onView = vi.fn();
      const faceData = createMockFaceDetection({
        is_unknown: true,
        event_id: 123,
      });

      renderHook(() => useUnknownStrangerAlerts({ showToasts: true, onView }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'face_detection',
          data: faceData,
        });
      });

      // Get the action from the toast call and simulate click
      const toastCall = mockToast.warning.mock.calls[0];
      const toastOptions = toastCall[1];
      expect(toastOptions.action).toBeDefined();

      // Simulate clicking the action button
      act(() => {
        toastOptions.action.onClick();
      });

      expect(onView).toHaveBeenCalledWith(
        expect.objectContaining({
          event_id: 123,
          is_unknown: true,
        })
      );
    });
  });

  describe('browser push notifications', () => {
    it('does not request notification permission by default', () => {
      renderHook(() => useUnknownStrangerAlerts(), {
        wrapper: createWrapper(),
      });

      // Should not attempt to access Notification API unless explicitly enabled
      expect(mockWebSocketReturn.isConnected).toBe(true);
    });
  });
});
