/**
 * useRecentThreats - Hook for managing recent threat detections with WebSocket updates
 *
 * This hook subscribes to WebSocket threat events and maintains a list of recent
 * threats filtered to the last 24 hours. It provides real-time updates when new
 * threats are detected.
 *
 * @module hooks/useRecentThreats
 */

import { useState, useCallback, useEffect, useRef } from 'react';

import { useWebSocket, type WebSocketOptions } from './useWebSocket';

import type {
  RecentThreat,
  UseRecentThreatsReturn,
  UseRecentThreatsOptions,
} from '@/types/threat';

import { logger } from '@/services/logger';


// ============================================================================
// Constants
// ============================================================================

const DEFAULT_WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws/events';

const DEFAULT_MAX_AGE_HOURS = 24;

// ============================================================================
// Type Guards
// ============================================================================

/**
 * WebSocket message envelope for threat detections
 */
interface WebSocketThreatMessage {
  type: 'threat_detected';
  data: {
    id: string;
    event_id: string;
    weapon_type: string;
    camera_name: string;
    timestamp: string;
    confidence: number;
    thumbnail_url?: string;
  };
}

/**
 * Type guard for threat detection WebSocket messages
 */
function isThreatMessage(value: unknown): value is WebSocketThreatMessage {
  if (typeof value !== 'object' || value === null) return false;
  const obj = value as Record<string, unknown>;

  if (obj.type !== 'threat_detected') return false;
  if (!obj.data || typeof obj.data !== 'object') return false;

  const data = obj.data as Record<string, unknown>;
  return (
    typeof data.id === 'string' &&
    typeof data.event_id === 'string' &&
    typeof data.weapon_type === 'string' &&
    typeof data.camera_name === 'string' &&
    typeof data.timestamp === 'string' &&
    typeof data.confidence === 'number'
  );
}

/**
 * Convert WebSocket threat data to RecentThreat interface
 */
function toRecentThreat(data: WebSocketThreatMessage['data']): RecentThreat {
  return {
    id: data.id,
    eventId: data.event_id,
    weaponType: data.weapon_type,
    cameraName: data.camera_name,
    timestamp: data.timestamp,
    confidence: data.confidence,
    thumbnailUrl: data.thumbnail_url,
  };
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Filter threats to only include those within the specified age window
 */
function filterByAge(threats: RecentThreat[], maxAgeHours: number): RecentThreat[] {
  const cutoff = Date.now() - maxAgeHours * 60 * 60 * 1000;
  return threats.filter((threat) => {
    const timestamp = new Date(threat.timestamp).getTime();
    return timestamp >= cutoff;
  });
}

/**
 * Sort threats by timestamp, most recent first
 */
function sortByTimestamp(threats: RecentThreat[]): RecentThreat[] {
  return [...threats].sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime();
    const timeB = new Date(b.timestamp).getTime();
    return timeB - timeA;
  });
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to track recent threat detections with WebSocket updates.
 *
 * Maintains a list of threats from the last 24 hours (configurable) and
 * provides real-time updates when new threats are detected via WebSocket.
 *
 * @param options - Configuration options
 * @returns Recent threats state and control functions
 *
 * @example
 * ```tsx
 * const { threats, count, isConnected, hasNewThreat } = useRecentThreats({
 *   onNewThreat: (threat) => {
 *     console.log('New threat:', threat.weaponType, threat.cameraName);
 *     playAlertSound();
 *   },
 *   maxAgeHours: 12, // Only show last 12 hours
 * });
 * ```
 */
export function useRecentThreats(
  options: UseRecentThreatsOptions = {}
): UseRecentThreatsReturn {
  const { onNewThreat, maxAgeHours = DEFAULT_MAX_AGE_HOURS } = options;

  // State
  const [threats, setThreats] = useState<RecentThreat[]>([]);
  const [hasNewThreat, setHasNewThreat] = useState(false);

  // Refs to avoid stale closures
  const onNewThreatRef = useRef(onNewThreat);
  const maxAgeHoursRef = useRef(maxAgeHours);

  // Update refs when options change
  useEffect(() => {
    onNewThreatRef.current = onNewThreat;
    maxAgeHoursRef.current = maxAgeHours;
  });

  // Clear the new threat flag
  const clearNewThreatFlag = useCallback(() => {
    setHasNewThreat(false);
  }, []);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback((data: unknown) => {
    // Check if this is a threat message
    if (!isThreatMessage(data)) {
      return;
    }

    const threatData = toRecentThreat(data.data);

    // Log the event
    logger.debug('Threat WebSocket event received', {
      component: 'useRecentThreats',
      threatId: threatData.id,
      weaponType: threatData.weaponType,
      cameraName: threatData.cameraName,
    });

    // Add to threats list
    setThreats((prev) => {
      // Check for duplicates
      if (prev.some((t) => t.id === threatData.id)) {
        return prev;
      }

      // Add new threat and filter by age
      const updated = [threatData, ...prev];
      const filtered = filterByAge(updated, maxAgeHoursRef.current);
      return sortByTimestamp(filtered);
    });

    // Set new threat flag for animation
    setHasNewThreat(true);

    // Call the callback
    onNewThreatRef.current?.(threatData);
  }, []);

  // Configure WebSocket options
  const wsOptions: WebSocketOptions = {
    url: DEFAULT_WS_URL,
    onMessage: handleMessage,
    reconnect: true,
    reconnectInterval: 1000,
    reconnectAttempts: 15,
    connectionTimeout: 10000,
    autoRespondToHeartbeat: true,
  };

  // Use the base WebSocket hook
  const { isConnected } = useWebSocket(wsOptions);

  // Periodically filter out old threats
  useEffect(() => {
    const interval = setInterval(() => {
      setThreats((prev) => filterByAge(prev, maxAgeHoursRef.current));
    }, 60 * 1000); // Check every minute

    return () => clearInterval(interval);
  }, []);

  return {
    threats,
    count: threats.length,
    isConnected,
    hasNewThreat,
    clearNewThreatFlag,
  };
}

export default useRecentThreats;
