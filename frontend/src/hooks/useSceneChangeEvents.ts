/**
 * useSceneChangeEvents - Hook for handling scene change WebSocket events with toast notifications
 *
 * This hook subscribes to SCENE_CHANGE_DETECTED WebSocket events and provides:
 * - Toast notifications when scene changes are detected
 * - Camera activity tracking for status indicators
 * - Camera name resolution for user-friendly notifications
 *
 * @module hooks/useSceneChangeEvents
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useCamerasQuery } from './useCamerasQuery';
import { formatChangeType, getChangeSeverity } from './useSceneChangeAlerts';
import { useToast } from './useToast';
import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { isSceneChangeMessage } from '../types/generated/websocket';

import type { WebSocketSceneChangeData } from '../types/generated/websocket';

// ============================================================================
// Types
// ============================================================================

/**
 * Scene change event data with camera name resolved.
 */
export interface SceneChangeEventData {
  /** Scene change record ID */
  id: number;
  /** Camera ID where change was detected */
  cameraId: string;
  /** Human-readable camera name (resolved from cameras query) */
  cameraName: string;
  /** When the change was detected (ISO 8601) */
  detectedAt: string;
  /** Type of change (view_blocked, angle_changed, view_tampered, unknown) */
  changeType: string;
  /** SSIM similarity score (0-1, lower = more different from baseline) */
  similarityScore: number;
  /** When this event was received */
  receivedAt: Date;
}

/**
 * Camera activity state for status indicators.
 */
export interface CameraActivityState {
  /** Camera ID */
  cameraId: string;
  /** Camera name */
  cameraName: string;
  /** When the last scene change was detected */
  lastActivityAt: Date;
  /** Type of the last scene change */
  lastChangeType: string;
  /** Whether the activity indicator is currently visible (within timeout) */
  isActive: boolean;
}

/**
 * Options for the useSceneChangeEvents hook.
 */
export interface UseSceneChangeEventsOptions {
  /**
   * Whether to enable the WebSocket connection.
   * @default true
   */
  enabled?: boolean;

  /**
   * Whether to show toast notifications for scene changes.
   * @default true
   */
  showToasts?: boolean;

  /**
   * Duration in milliseconds to keep the activity indicator active.
   * @default 30000 (30 seconds)
   */
  activityTimeoutMs?: number;

  /**
   * Callback when a scene change event is received.
   */
  onSceneChange?: (event: SceneChangeEventData) => void;

  /**
   * Maximum number of recent events to track.
   * @default 50
   */
  maxRecentEvents?: number;
}

/**
 * Return type for the useSceneChangeEvents hook.
 */
export interface UseSceneChangeEventsReturn {
  /** Map of camera ID to activity state */
  cameraActivity: Record<string, CameraActivityState>;
  /** List of camera IDs with recent scene change activity */
  activeCameraIds: string[];
  /** List of recent scene change events */
  recentEvents: SceneChangeEventData[];
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Total count of scene changes since hook mounted */
  totalEventCount: number;
  /** Check if a specific camera has recent activity */
  hasRecentActivity: (cameraId: string) => boolean;
  /** Get the activity state for a specific camera */
  getActivityState: (cameraId: string) => CameraActivityState | undefined;
  /** Clear activity state for a specific camera */
  clearActivity: (cameraId: string) => void;
  /** Clear all activity states */
  clearAllActivity: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/** Default activity timeout in milliseconds (30 seconds) */
const DEFAULT_ACTIVITY_TIMEOUT_MS = 30000;

/** Default maximum recent events to track */
const DEFAULT_MAX_RECENT_EVENTS = 50;

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for handling scene change WebSocket events with toast notifications
 * and camera activity tracking.
 *
 * @param options - Configuration options
 * @returns Scene change event state and helpers
 *
 * @example
 * ```tsx
 * function CameraMonitor() {
 *   const { activeCameraIds, hasRecentActivity } = useSceneChangeEvents({
 *     showToasts: true,
 *     activityTimeoutMs: 30000,
 *   });
 *
 *   return (
 *     <CameraGrid
 *       cameras={cameras}
 *       highlightedCameraIds={activeCameraIds}
 *     />
 *   );
 * }
 * ```
 */
export function useSceneChangeEvents(
  options: UseSceneChangeEventsOptions = {}
): UseSceneChangeEventsReturn {
  const {
    enabled = true,
    showToasts = true,
    activityTimeoutMs = DEFAULT_ACTIVITY_TIMEOUT_MS,
    onSceneChange,
    maxRecentEvents = DEFAULT_MAX_RECENT_EVENTS,
  } = options;

  // State
  const [cameraActivity, setCameraActivity] = useState<Record<string, CameraActivityState>>({});
  const [recentEvents, setRecentEvents] = useState<SceneChangeEventData[]>([]);
  const [totalEventCount, setTotalEventCount] = useState(0);

  // Refs for callbacks to avoid stale closures
  const onSceneChangeRef = useRef(onSceneChange);
  const activityTimeoutMsRef = useRef(activityTimeoutMs);
  const showToastsRef = useRef(showToasts);
  const timeoutIdsRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Update refs when options change
  useEffect(() => {
    onSceneChangeRef.current = onSceneChange;
    activityTimeoutMsRef.current = activityTimeoutMs;
    showToastsRef.current = showToasts;
  });

  // Get cameras for name lookup
  const { cameras } = useCamerasQuery({ enabled });

  // Build camera name lookup map
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const camera of cameras) {
      map.set(camera.id, camera.name);
    }
    return map;
  }, [cameras]);

  // Toast hook
  const toast = useToast();

  // Resolve camera name from ID
  const resolveCameraName = useCallback(
    (cameraId: string): string => {
      return cameraNameMap.get(cameraId) ?? cameraId;
    },
    [cameraNameMap]
  );

  // Clear activity for a specific camera
  const clearActivity = useCallback((cameraId: string) => {
    setCameraActivity((prev) => {
      const next = { ...prev };
      if (next[cameraId]) {
        next[cameraId] = { ...next[cameraId], isActive: false };
      }
      return next;
    });

    // Clear any pending timeout
    const timeoutId = timeoutIdsRef.current.get(cameraId);
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutIdsRef.current.delete(cameraId);
    }
  }, []);

  // Clear all activity
  const clearAllActivity = useCallback(() => {
    setCameraActivity((prev) => {
      const next: Record<string, CameraActivityState> = {};
      for (const [id, state] of Object.entries(prev)) {
        next[id] = { ...state, isActive: false };
      }
      return next;
    });

    // Clear all pending timeouts
    timeoutIdsRef.current.forEach((timeoutId) => {
      clearTimeout(timeoutId);
    });
    timeoutIdsRef.current.clear();
  }, []);

  // Handle incoming scene change messages
  const handleMessage = useCallback(
    (data: unknown) => {
      // Check for both legacy 'scene_change' and hierarchical 'scene_change.detected' formats
      // The isSceneChangeMessage type guard handles the legacy format
      if (!isSceneChangeMessage(data)) {
        // Also check for hierarchical format
        const msg = data as { type?: string; payload?: WebSocketSceneChangeData };
        if (msg?.type !== 'scene_change.detected' || !msg.payload) {
          return;
        }

        // Handle hierarchical format
        const sceneData = msg.payload;
        const cameraName = resolveCameraName(sceneData.camera_id);

        const eventData: SceneChangeEventData = {
          id: sceneData.id,
          cameraId: sceneData.camera_id,
          cameraName,
          detectedAt: sceneData.detected_at,
          changeType: sceneData.change_type,
          similarityScore: sceneData.similarity_score,
          receivedAt: new Date(),
        };

        processSceneChangeEvent(eventData);
        return;
      }

      // Handle legacy format
      const sceneData: WebSocketSceneChangeData = data.data;
      const cameraName = resolveCameraName(sceneData.camera_id);

      const eventData: SceneChangeEventData = {
        id: sceneData.id,
        cameraId: sceneData.camera_id,
        cameraName,
        detectedAt: sceneData.detected_at,
        changeType: sceneData.change_type,
        similarityScore: sceneData.similarity_score,
        receivedAt: new Date(),
      };

      processSceneChangeEvent(eventData);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- processSceneChangeEvent uses refs, stable enough
    [resolveCameraName]
  );

  // Process a scene change event (shared logic)
  const processSceneChangeEvent = useCallback(
    (eventData: SceneChangeEventData) => {
      // Update total count
      setTotalEventCount((prev) => prev + 1);

      // Add to recent events (avoiding duplicates by ID)
      setRecentEvents((prev) => {
        if (prev.some((e) => e.id === eventData.id)) {
          return prev;
        }
        const updated = [eventData, ...prev];
        return updated.slice(0, maxRecentEvents);
      });

      // Update camera activity state
      const activityState: CameraActivityState = {
        cameraId: eventData.cameraId,
        cameraName: eventData.cameraName,
        lastActivityAt: eventData.receivedAt,
        lastChangeType: eventData.changeType,
        isActive: true,
      };

      setCameraActivity((prev) => ({
        ...prev,
        [eventData.cameraId]: activityState,
      }));

      // Clear any existing timeout for this camera
      const existingTimeout = timeoutIdsRef.current.get(eventData.cameraId);
      if (existingTimeout) {
        clearTimeout(existingTimeout);
      }

      // Set timeout to clear activity indicator
      const timeoutId = setTimeout(() => {
        setCameraActivity((prev) => {
          const next = { ...prev };
          if (next[eventData.cameraId]) {
            next[eventData.cameraId] = { ...next[eventData.cameraId], isActive: false };
          }
          return next;
        });
        timeoutIdsRef.current.delete(eventData.cameraId);
      }, activityTimeoutMsRef.current);

      timeoutIdsRef.current.set(eventData.cameraId, timeoutId);

      // Show toast notification
      if (showToastsRef.current) {
        const severity = getChangeSeverity(eventData.changeType);
        const changeTypeDisplay = formatChangeType(eventData.changeType);
        const message = `Scene change detected on ${eventData.cameraName}`;
        const description = `${changeTypeDisplay} (similarity: ${Math.round(eventData.similarityScore * 100)}%)`;

        if (severity === 'high') {
          toast.warning(message, { description, duration: 8000 });
        } else if (severity === 'medium') {
          toast.info(message, { description, duration: 5000 });
        } else {
          toast.info(message, { description, duration: 4000 });
        }
      }

      // Call external callback
      onSceneChangeRef.current?.(eventData);
    },
    [maxRecentEvents, toast]
  );

  // Build WebSocket options
  const wsOptions = buildWebSocketOptions('/ws/events');

  // Subscribe to WebSocket
  const { isConnected } = useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
    reconnect: true,
    reconnectInterval: 1000,
    reconnectAttempts: 15,
  });

  // Cleanup timeouts on unmount
  useEffect(() => {
    const timeoutIds = timeoutIdsRef.current;
    return () => {
      timeoutIds.forEach((timeoutId) => {
        clearTimeout(timeoutId);
      });
      timeoutIds.clear();
    };
  }, []);

  // Computed values
  const activeCameraIds = useMemo(
    () =>
      Object.entries(cameraActivity)
        .filter(([, state]) => state.isActive)
        .map(([id]) => id),
    [cameraActivity]
  );

  const hasRecentActivity = useCallback(
    (cameraId: string): boolean => {
      return cameraActivity[cameraId]?.isActive ?? false;
    },
    [cameraActivity]
  );

  const getActivityState = useCallback(
    (cameraId: string): CameraActivityState | undefined => {
      return cameraActivity[cameraId];
    },
    [cameraActivity]
  );

  return {
    cameraActivity,
    activeCameraIds,
    recentEvents,
    isConnected,
    totalEventCount,
    hasRecentActivity,
    getActivityState,
    clearActivity,
    clearAllActivity,
  };
}

export default useSceneChangeEvents;
