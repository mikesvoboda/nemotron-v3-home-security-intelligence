/**
 * Hook for tracking unacknowledged scene change alerts from WebSocket.
 *
 * This hook subscribes to the /ws/events channel and listens for scene_change
 * messages. It tracks unacknowledged scene changes and provides:
 * - Count of unacknowledged scene changes
 * - List of recent scene change alerts
 * - Ability to dismiss/acknowledge alerts locally
 *
 * Scene changes indicate potential camera tampering and should be reviewed.
 */
import { useState, useCallback, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { isSceneChangeMessage } from '../types/generated/websocket';

import type { WebSocketSceneChangeData } from '../types/generated/websocket';

/**
 * Scene change alert with local tracking state.
 */
export interface SceneChangeAlert {
  /** Unique scene change ID */
  id: number;
  /** Camera ID where change was detected */
  cameraId: string;
  /** When the change was detected */
  detectedAt: string;
  /** Type of change (view_blocked, angle_changed, view_tampered) */
  changeType: string;
  /** SSIM score (0-1, lower = more different from baseline) */
  similarityScore: number;
  /** Whether the alert has been dismissed locally */
  dismissed: boolean;
  /** When the alert was received */
  receivedAt: Date;
}

export interface UseSceneChangeAlertsOptions {
  /** Maximum number of alerts to keep in memory */
  maxAlerts?: number;
  /** Auto-dismiss alerts after this many milliseconds (0 = never) */
  autoDismissMs?: number;
}

export interface UseSceneChangeAlertsReturn {
  /** List of all scene change alerts (including dismissed) */
  alerts: SceneChangeAlert[];
  /** Count of undismissed alerts */
  unacknowledgedCount: number;
  /** Whether there are any undismissed alerts */
  hasAlerts: boolean;
  /** Dismiss a specific alert by ID */
  dismissAlert: (id: number) => void;
  /** Dismiss all alerts */
  dismissAll: () => void;
  /** Acknowledge a specific alert (alias for dismissAlert) */
  acknowledgeAlert: (id: number) => void;
  /** Acknowledge all alerts (alias for dismissAll) */
  acknowledgeAll: () => void;
  /** Clear all alerts from memory */
  clearAlerts: () => void;
  /** WebSocket connection status */
  isConnected: boolean;
  /** Whether any camera has a blocked view */
  hasBlockedCameras: boolean;
  /** Whether any camera has been tampered with */
  hasTamperedCameras: boolean;
  /** Camera IDs with blocked views */
  blockedCameraIds: string[];
  /** Camera IDs with tampered views */
  tamperedCameraIds: string[];
}

const DEFAULT_MAX_ALERTS = 50;

/**
 * Format change type for display.
 */
export function formatChangeType(changeType: string): string {
  switch (changeType) {
    case 'view_blocked':
      return 'View Blocked';
    case 'angle_changed':
      return 'Angle Changed';
    case 'view_tampered':
      return 'View Tampered';
    default:
      return 'Unknown';
  }
}

/**
 * Get severity level for a change type.
 */
export function getChangeSeverity(changeType: string): 'high' | 'medium' | 'low' {
  switch (changeType) {
    case 'view_blocked':
    case 'view_tampered':
      return 'high';
    case 'angle_changed':
      return 'medium';
    default:
      return 'low';
  }
}

/**
 * Hook to subscribe to scene change alerts from WebSocket.
 *
 * @param options - Configuration options
 * @returns Scene change alert state and actions
 *
 * @example
 * ```tsx
 * function Header() {
 *   const { hasAlerts, unacknowledgedCount, dismissAll } = useSceneChangeAlerts();
 *
 *   return (
 *     <div>
 *       {hasAlerts && (
 *         <Badge count={unacknowledgedCount} onClick={dismissAll}>
 *           Scene Changes
 *         </Badge>
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function useSceneChangeAlerts(
  options: UseSceneChangeAlertsOptions = {}
): UseSceneChangeAlertsReturn {
  const { maxAlerts = DEFAULT_MAX_ALERTS } = options;

  const [alerts, setAlerts] = useState<SceneChangeAlert[]>([]);

  const handleMessage = useCallback(
    (data: unknown) => {
      if (isSceneChangeMessage(data)) {
        const sceneData: WebSocketSceneChangeData = data.data;

        const newAlert: SceneChangeAlert = {
          id: sceneData.id,
          cameraId: sceneData.camera_id,
          detectedAt: sceneData.detected_at,
          changeType: sceneData.change_type,
          similarityScore: sceneData.similarity_score,
          dismissed: false,
          receivedAt: new Date(),
        };

        setAlerts((prev) => {
          // Avoid duplicates by checking ID
          if (prev.some((alert) => alert.id === newAlert.id)) {
            return prev;
          }

          // Add new alert at the beginning, trim to max size
          const updated = [newAlert, ...prev];
          return updated.slice(0, maxAlerts);
        });
      }
    },
    [maxAlerts]
  );

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  const wsOptions = buildWebSocketOptions('/ws/events');

  const { isConnected } = useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  const dismissAlert = useCallback((id: number) => {
    setAlerts((prev) =>
      prev.map((alert) => (alert.id === id ? { ...alert, dismissed: true } : alert))
    );
  }, []);

  const dismissAll = useCallback(() => {
    setAlerts((prev) => prev.map((alert) => ({ ...alert, dismissed: true })));
  }, []);

  const clearAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  const unacknowledgedCount = useMemo(
    () => alerts.filter((alert) => !alert.dismissed).length,
    [alerts]
  );

  const hasAlerts = unacknowledgedCount > 0;

  // Computed flags for blocked/tampered cameras (only unacknowledged alerts)
  const blockedCameraIds = useMemo(
    () =>
      [...new Set(
        alerts
          .filter((alert) => !alert.dismissed && alert.changeType === 'view_blocked')
          .map((alert) => alert.cameraId)
      )],
    [alerts]
  );

  const tamperedCameraIds = useMemo(
    () =>
      [...new Set(
        alerts
          .filter((alert) => !alert.dismissed && alert.changeType === 'view_tampered')
          .map((alert) => alert.cameraId)
      )],
    [alerts]
  );

  const hasBlockedCameras = blockedCameraIds.length > 0;
  const hasTamperedCameras = tamperedCameraIds.length > 0;

  return {
    alerts,
    unacknowledgedCount,
    hasAlerts,
    dismissAlert,
    dismissAll,
    acknowledgeAlert: dismissAlert,
    acknowledgeAll: dismissAll,
    clearAlerts,
    isConnected,
    hasBlockedCameras,
    hasTamperedCameras,
    blockedCameraIds,
    tamperedCameraIds,
  };
}

export default useSceneChangeAlerts;
