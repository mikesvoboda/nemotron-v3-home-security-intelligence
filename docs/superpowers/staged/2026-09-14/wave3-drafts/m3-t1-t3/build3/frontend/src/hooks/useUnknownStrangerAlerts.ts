/**
 * useUnknownStrangerAlerts - WebSocket hook for real-time unknown stranger alerts (NEM-4688 Phase 4)
 *
 * This hook subscribes to WebSocket face detection events and provides real-time
 * alerts when unknown persons are detected. Features include:
 * - Toast notifications for unknown face detections
 * - Unread count badge for UI indicators
 * - Optional browser push notifications (when permitted)
 * - Automatic cache invalidation for unknown strangers queries
 *
 * Events handled:
 * - face_detection: New face detected (filtered for is_unknown=true)
 *
 * @module hooks/useUnknownStrangerAlerts
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useCallback, useRef, useState } from 'react';

import { faceRecognitionQueryKeys } from './useFaceRecognitionApi';
import { useToast } from './useToast';
import { useWebSocket, type WebSocketOptions } from './useWebSocket';
import { logger } from '../services/logger';

// ============================================================================
// Types
// ============================================================================

/**
 * WebSocket payload for face detection events.
 * Matches the expected message format from the backend.
 */
export interface FaceDetectionWebSocketPayload {
  /** ID of the face detection event */
  event_id: number;
  /** ID of the camera that captured the face */
  camera_id: number;
  /** Display name of the camera */
  camera_name: string;
  /** Whether this face is from an unknown person */
  is_unknown: boolean;
  /** ISO 8601 timestamp when the face was detected */
  timestamp: string;
  /** URL to the face thumbnail image */
  thumbnail_url?: string | null;
  /** Quality score of the detected face (0-1) */
  quality_score?: number;
  /** ID of matched known person (if known) */
  matched_person_id?: number | null;
  /** Name of matched known person (if known) */
  matched_person_name?: string | null;
  /** Match confidence score (0-1) for known persons */
  match_confidence?: number | null;
}

/**
 * Unknown face event handler callback type
 */
export type UnknownFaceEventHandler = (face: FaceDetectionWebSocketPayload) => void;

/**
 * Options for configuring the useUnknownStrangerAlerts hook
 */
export interface UseUnknownStrangerAlertsOptions {
  /**
   * WebSocket URL to connect to
   * @default process.env.VITE_WS_URL || 'ws://localhost:8000/ws/events'
   */
  url?: string;

  /**
   * Whether to automatically invalidate React Query cache on unknown face events
   * @default true
   */
  autoInvalidateCache?: boolean;

  /**
   * Whether to show toast notifications for unknown face detections
   * @default true
   */
  showToasts?: boolean;

  /**
   * Called when an unknown face is detected
   */
  onUnknownDetected?: UnknownFaceEventHandler;

  /**
   * Called when the user clicks "View" on a toast notification
   */
  onView?: UnknownFaceEventHandler;

  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;
}

/**
 * Return type for the useUnknownStrangerAlerts hook
 */
export interface UseUnknownStrangerAlertsReturn {
  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** The last unknown face detection received */
  lastUnknownFace: FaceDetectionWebSocketPayload | null;

  /** Number of unread unknown stranger alerts */
  unreadCount: number;

  /** Mark all alerts as read (resets unread count) */
  markAsRead: () => void;

  /** Whether max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;

  /** Current reconnection attempt count */
  reconnectCount: number;
}

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for unknown stranger alerts.
 */
export const unknownStrangerAlertsQueryKeys = {
  /** Base key for all unknown stranger alerts queries */
  all: ['unknown-stranger-alerts'] as const,
  /** Unread count */
  unreadCount: () => [...unknownStrangerAlertsQueryKeys.all, 'unread-count'] as const,
};

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a message is a face detection message
 */
function isFaceDetectionMessage(
  data: unknown
): data is { type: string; data: FaceDetectionWebSocketPayload } {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  if (msg.type !== 'face_detection') {
    return false;
  }

  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const payload = msg.data as Record<string, unknown>;

  return (
    typeof payload.event_id === 'number' &&
    typeof payload.camera_id === 'number' &&
    typeof payload.camera_name === 'string' &&
    typeof payload.is_unknown === 'boolean' &&
    typeof payload.timestamp === 'string'
  );
}

// ============================================================================
// Hook Implementation
// ============================================================================

const DEFAULT_WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws/events';

/**
 * Hook to subscribe to real-time unknown stranger alert WebSocket events.
 *
 * Automatically invalidates React Query cache for unknown strangers and face stats
 * when events are received, ensuring the UI stays in sync with server state.
 *
 * @param options - Configuration options
 * @returns WebSocket connection state, unread count, and handlers
 *
 * @example
 * ```tsx
 * const { isConnected, lastUnknownFace, unreadCount, markAsRead } = useUnknownStrangerAlerts({
 *   onUnknownDetected: (face) => {
 *     console.log('Unknown face detected:', face.camera_name);
 *   },
 *   onView: (face) => {
 *     navigate(`/face-recognition?event=${face.event_id}`);
 *   },
 *   showToasts: true,
 * });
 * ```
 */
export function useUnknownStrangerAlerts(
  options: UseUnknownStrangerAlertsOptions = {}
): UseUnknownStrangerAlertsReturn {
  const {
    url: urlOption = DEFAULT_WS_URL,
    autoInvalidateCache = true,
    showToasts = true,
    onUnknownDetected,
    onView,
    enabled = true,
  } = options;
  const url: string = urlOption;

  const queryClient = useQueryClient();
  const toast = useToast();

  // Track last unknown face and unread count using useState for re-renders
  const [lastUnknownFace, setLastUnknownFace] = useState<FaceDetectionWebSocketPayload | null>(
    null
  );
  const [unreadCount, setUnreadCount] = useState(0);

  // Store callbacks in refs to avoid stale closures
  const onUnknownDetectedRef = useRef(onUnknownDetected);
  const onViewRef = useRef(onView);
  const showToastsRef = useRef(showToasts);

  // Update refs when callbacks change
  useEffect(() => {
    onUnknownDetectedRef.current = onUnknownDetected;
    onViewRef.current = onView;
    showToastsRef.current = showToasts;
  });

  // Mark all alerts as read
  const markAsRead = useCallback(() => {
    setUnreadCount(0);
  }, []);

  // Invalidate face recognition caches
  const invalidateFaceRecognitionCache = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: faceRecognitionQueryKeys.unknownStrangers(),
    });
    void queryClient.invalidateQueries({
      queryKey: faceRecognitionQueryKeys.faceStats(),
    });
  }, [queryClient]);

  // Format relative time for toast
  const formatRelativeTime = useCallback((timestamp: string): string => {
    const now = new Date();
    const eventTime = new Date(timestamp);
    const diffMs = now.getTime() - eventTime.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);

    if (diffSeconds < 5) {
      return 'Just now';
    } else if (diffSeconds < 60) {
      return `${diffSeconds}s ago`;
    } else if (diffSeconds < 3600) {
      const mins = Math.floor(diffSeconds / 60);
      return `${mins}m ago`;
    } else {
      return eventTime.toLocaleTimeString();
    }
  }, []);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      // Check if this is a face detection message
      if (!isFaceDetectionMessage(data)) {
        return;
      }

      const faceMessage = data;
      const faceData = faceMessage.data;

      // Only process unknown faces
      if (!faceData.is_unknown) {
        return;
      }

      // Update state
      setLastUnknownFace(faceData);
      setUnreadCount((prev) => prev + 1);

      // Log the event
      logger.debug('Unknown stranger detected via WebSocket', {
        component: 'useUnknownStrangerAlerts',
        eventId: faceData.event_id,
        cameraName: faceData.camera_name,
        cameraId: faceData.camera_id,
        timestamp: faceData.timestamp,
      });

      // Show toast notification
      if (showToastsRef.current) {
        const relativeTime = formatRelativeTime(faceData.timestamp);
        toast.warning('Unknown Person Detected', {
          description: `${faceData.camera_name} - ${relativeTime}`,
          duration: 5000,
          action: {
            label: 'View',
            onClick: () => {
              onViewRef.current?.(faceData);
            },
          },
        });
      }

      // Call the handler
      onUnknownDetectedRef.current?.(faceData);

      // Invalidate cache to trigger refetch
      if (autoInvalidateCache) {
        invalidateFaceRecognitionCache();
      }
    },
    [autoInvalidateCache, invalidateFaceRecognitionCache, toast, formatRelativeTime]
  );

  // Configure WebSocket options
  const wsOptions: WebSocketOptions = {
    url,
    onMessage: handleMessage,
    reconnect: true,
    reconnectInterval: 1000,
    reconnectAttempts: 15,
    connectionTimeout: 10000,
    autoRespondToHeartbeat: true,
  };

  // Use the base WebSocket hook
  const { isConnected, disconnect, hasExhaustedRetries, reconnectCount } = useWebSocket(
    enabled ? wsOptions : { ...wsOptions, reconnect: false }
  );

  // Manual disconnect if not enabled
  useEffect(() => {
    if (!enabled) {
      disconnect();
    }
  }, [enabled, disconnect]);

  return {
    isConnected,
    lastUnknownFace,
    unreadCount,
    markAsRead,
    hasExhaustedRetries,
    reconnectCount,
  };
}

export default useUnknownStrangerAlerts;
