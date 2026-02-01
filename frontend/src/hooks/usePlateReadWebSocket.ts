/**
 * usePlateReadWebSocket - WebSocket hook for real-time plate read updates (NEM-4865)
 *
 * This hook subscribes to WebSocket plate read events and provides callbacks
 * for handling new plate detections from the ALPR (Automatic License Plate Recognition)
 * system.
 *
 * Events handled:
 * - plate_read.created: New license plate detected and stored
 *
 * @module hooks/usePlateReadWebSocket
 */

import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useCallback, useRef, useState } from 'react';

import { plateStatisticsQueryKeys } from './usePlateStatisticsQuery';
import { useToast } from './useToast';
import { useWebSocket, type WebSocketOptions } from './useWebSocket';
import { logger } from '../services/logger';

import type { PlateReadDetectedPayload } from '../types/websocket-events';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for plate reads queries.
 *
 * Keys follow a hierarchical pattern: ['plate-reads', ...]
 *
 * @example
 * // Invalidate all plate reads queries
 * queryClient.invalidateQueries({ queryKey: plateReadsQueryKeys.all });
 */
export const plateReadsQueryKeys = {
  /** Base key for all plate reads queries - use for bulk invalidation */
  all: ['plate-reads'] as const,
  /** List of plate reads with optional filters */
  lists: () => [...plateReadsQueryKeys.all, 'list'] as const,
  /** Single plate read by ID */
  detail: (id: number) => [...plateReadsQueryKeys.all, 'detail', id] as const,
  /** Search results */
  search: (text: string) => [...plateReadsQueryKeys.all, 'search', text] as const,
};

// ============================================================================
// Types
// ============================================================================

/**
 * Plate read event handler callback type
 */
export type PlateReadEventHandler = (plate: PlateReadDetectedPayload) => void;

/**
 * Options for configuring the usePlateReadWebSocket hook
 */
export interface UsePlateReadWebSocketOptions {
  /**
   * WebSocket URL to connect to
   * @default process.env.VITE_WS_URL || 'ws://localhost:8000/ws/events'
   */
  url?: string;

  /**
   * Whether to automatically invalidate React Query cache on plate read events
   * @default true
   */
  autoInvalidateCache?: boolean;

  /**
   * Whether to show toast notifications for new plate detections
   * @default false
   */
  showToasts?: boolean;

  /**
   * Called when a new plate read is detected
   */
  onPlateDetected?: PlateReadEventHandler;

  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;
}

/**
 * Return type for the usePlateReadWebSocket hook
 */
export interface UsePlateReadWebSocketReturn {
  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** The last plate read received */
  lastPlateRead: PlateReadDetectedPayload | null;

  /** The last event type received */
  lastEventType: string | null;

  /** Whether max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;

  /** Current reconnection attempt count */
  reconnectCount: number;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a message is a plate read message
 */
function isPlateReadMessage(data: unknown): data is { type: string; data: PlateReadDetectedPayload } {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  if (msg.type !== 'plate_read.created') {
    return false;
  }

  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const payload = msg.data as Record<string, unknown>;

  return (
    typeof payload.id === 'number' &&
    typeof payload.camera_id === 'string' &&
    typeof payload.plate_text === 'string' &&
    typeof payload.detection_confidence === 'number' &&
    typeof payload.ocr_confidence === 'number' &&
    typeof payload.timestamp === 'string'
  );
}

// ============================================================================
// Hook Implementation
// ============================================================================

const DEFAULT_WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws/events';

/**
 * Hook to subscribe to real-time plate read WebSocket events.
 *
 * Automatically invalidates React Query cache for plate reads and statistics
 * when events are received, ensuring the UI stays in sync with server state.
 *
 * @param options - Configuration options
 * @returns WebSocket connection state and handlers
 *
 * @example
 * ```tsx
 * const { isConnected, lastPlateRead } = usePlateReadWebSocket({
 *   onPlateDetected: (plate) => {
 *     console.log('New plate:', plate.plate_text);
 *     showNotification(`Plate ${plate.plate_text} detected`);
 *   },
 *   showToasts: true,
 * });
 * ```
 */
export function usePlateReadWebSocket(
  options: UsePlateReadWebSocketOptions = {}
): UsePlateReadWebSocketReturn {
  const {
    url: urlOption = DEFAULT_WS_URL,
    autoInvalidateCache = true,
    showToasts = false,
    onPlateDetected,
    enabled = true,
  } = options;
  const url: string = urlOption;

  const queryClient = useQueryClient();
  const toast = useToast();

  // Track last plate read state using useState for re-renders
  const [lastPlateRead, setLastPlateRead] = useState<PlateReadDetectedPayload | null>(null);
  const [lastEventType, setLastEventType] = useState<string | null>(null);

  // Store callbacks in refs to avoid stale closures
  const onPlateDetectedRef = useRef(onPlateDetected);
  const showToastsRef = useRef(showToasts);

  // Update refs when callbacks change
  useEffect(() => {
    onPlateDetectedRef.current = onPlateDetected;
    showToastsRef.current = showToasts;
  });

  // Invalidate plate reads and statistics cache to trigger refetch
  const invalidatePlateReadsCache = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: plateReadsQueryKeys.all });
    void queryClient.invalidateQueries({ queryKey: plateStatisticsQueryKeys.all });
  }, [queryClient]);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      // Check if this is a plate read message
      if (!isPlateReadMessage(data)) {
        return;
      }

      const plateMessage = data;
      const eventType = plateMessage.type;
      const plateData = plateMessage.data;

      // Update state to trigger re-renders
      setLastPlateRead(plateData);
      setLastEventType(eventType);

      // Log the event
      logger.debug('Plate read WebSocket event received', {
        component: 'usePlateReadWebSocket',
        eventType,
        plateId: plateData.id,
        plateText: plateData.plate_text,
        cameraId: plateData.camera_id,
        confidence: plateData.ocr_confidence,
      });

      // Show toast notification
      if (showToastsRef.current) {
        toast.success(`Plate detected: ${plateData.plate_text}`, { duration: 4000 });
      }

      // Call the handler
      onPlateDetectedRef.current?.(plateData);

      // Invalidate cache to trigger refetch
      if (autoInvalidateCache) {
        invalidatePlateReadsCache();
      }
    },
    [autoInvalidateCache, invalidatePlateReadsCache, toast]
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
    lastPlateRead,
    lastEventType,
    hasExhaustedRetries,
    reconnectCount,
  };
}

export default usePlateReadWebSocket;
