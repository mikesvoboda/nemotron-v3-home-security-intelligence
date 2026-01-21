/**
 * useZonePresence - Hook for tracking household member presence in a zone
 *
 * This hook subscribes to WebSocket detection events and matches them against
 * household members to track who is currently present in a specific zone.
 *
 * Features:
 * - Real-time WebSocket subscription for detection events
 * - Entity matching to household members
 * - Configurable presence timeout (staleness threshold)
 * - Active vs stale presence distinction
 *
 * @module hooks/useZonePresence
 *
 * @example
 * ```tsx
 * function ZoneComponent({ zoneId }: { zoneId: string }) {
 *   const { members, isConnected } = useZonePresence(zoneId);
 *
 *   return (
 *     <div>
 *       {members.map(member => (
 *         <span key={member.id} className={member.isStale ? 'opacity-50' : ''}>
 *           {member.name}
 *         </span>
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMembersQuery, type HouseholdMember } from './useHouseholdApi';
import { useWebSocketEvents } from './useWebSocketEvent';
import { WSEventType } from '../types/websocket-events';

import type { DetectionNewPayload, EventCreatedPayload } from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Presence state for a household member in a zone.
 */
export interface ZonePresenceMember {
  /** Household member ID */
  id: number;
  /** Member name */
  name: string;
  /** Member role */
  role: HouseholdMember['role'];
  /** Last detected timestamp (ISO string) */
  lastSeen: string;
  /** Whether the presence is stale (detected more than staleThresholdMs ago) */
  isStale: boolean;
  /** Whether the presence is active (pulse animation) - detected within activeThresholdMs */
  isActive: boolean;
  /** Entity ID that matched this member (if available) */
  entityId?: string;
}

/**
 * Detection record for internal tracking.
 */
interface DetectionRecord {
  memberId: number;
  entityId?: string;
  timestamp: string;
  zoneId: string;
}

/**
 * Options for the useZonePresence hook.
 */
export interface UseZonePresenceOptions {
  /**
   * Time in milliseconds after which presence is considered stale.
   * @default 300000 (5 minutes)
   */
  staleThresholdMs?: number;

  /**
   * Time in milliseconds during which presence is considered active.
   * Active presence shows pulse animation.
   * @default 30000 (30 seconds)
   */
  activeThresholdMs?: number;

  /**
   * Whether to enable the WebSocket subscription.
   * @default true
   */
  enabled?: boolean;

  /**
   * Interval for cleaning up expired presence records.
   * @default 60000 (1 minute)
   */
  cleanupIntervalMs?: number;
}

/**
 * Return type for the useZonePresence hook.
 */
export interface UseZonePresenceReturn {
  /** List of members currently present in the zone */
  members: ZonePresenceMember[];
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Whether data is loading (household members) */
  isLoading: boolean;
  /** Error from household members query */
  error: Error | null;
  /** Total count of present members */
  presentCount: number;
  /** Count of active (recently detected) members */
  activeCount: number;
  /** Manually clear all presence records for this zone */
  clearPresence: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/** Default stale threshold: 5 minutes */
const DEFAULT_STALE_THRESHOLD_MS = 5 * 60 * 1000;

/** Default active threshold: 30 seconds */
const DEFAULT_ACTIVE_THRESHOLD_MS = 30 * 1000;

/** Default cleanup interval: 1 minute */
const DEFAULT_CLEANUP_INTERVAL_MS = 60 * 1000;

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for tracking household member presence in a zone.
 *
 * Subscribes to WebSocket detection events and matches detected entities
 * against household members. Presence records are tracked with timestamps
 * to distinguish between active, recent, and stale presence.
 *
 * @param zoneId - ID of the zone to track presence for
 * @param options - Configuration options
 * @returns Presence data and WebSocket connection state
 *
 * @example
 * ```tsx
 * const { members, isConnected, presentCount } = useZonePresence('zone-123', {
 *   staleThresholdMs: 10 * 60 * 1000, // 10 minutes
 *   activeThresholdMs: 60 * 1000, // 1 minute
 * });
 * ```
 */
export function useZonePresence(
  zoneId: string,
  options: UseZonePresenceOptions = {}
): UseZonePresenceReturn {
  const {
    staleThresholdMs = DEFAULT_STALE_THRESHOLD_MS,
    activeThresholdMs = DEFAULT_ACTIVE_THRESHOLD_MS,
    enabled = true,
    cleanupIntervalMs = DEFAULT_CLEANUP_INTERVAL_MS,
  } = options;

  // Fetch household members for matching
  const { data: householdMembers, isLoading, error } = useMembersQuery();

  // Track detection records by member ID
  const [detectionRecords, setDetectionRecords] = useState<Map<number, DetectionRecord>>(new Map());

  // Refs for stale closure prevention
  const zoneIdRef = useRef(zoneId);
  const householdMembersRef = useRef(householdMembers);

  useEffect(() => {
    zoneIdRef.current = zoneId;
    householdMembersRef.current = householdMembers;
  });

  /**
   * Match detection to household member.
   * In a real implementation, this would use entity matching (face recognition,
   * appearance matching, etc.). For now, we use a simplified approach that
   * tracks any person detection in the zone.
   */
  const matchDetectionToMember = useCallback(
    (detection: { label: string; entityId?: string; zoneId?: string }) => {
      const members = householdMembersRef.current;
      if (!members || members.length === 0) return null;

      // Only process detections for the target zone
      // In real implementation, detection would include zone_id
      // For now, we'll check if the detection.zoneId matches

      // Person detections can be matched to residents
      if (detection.label === 'person') {
        // Simple matching: return first resident member
        // In production, this would use entity ID to face/appearance matching
        const residents = members.filter(
          (m) => m.role === 'resident' || m.role === 'family'
        );
        if (residents.length > 0) {
          return residents[0];
        }
      }

      return null;
    },
    []
  );

  /**
   * Handle new detection event.
   */
  const handleDetection = useCallback(
    (payload: DetectionNewPayload) => {
      const currentZoneId = zoneIdRef.current;

      // Check if detection has zone information
      // The payload may include zone_id from backend zone overlap detection
      const detectionZoneId = (payload as DetectionNewPayload & { zone_id?: string }).zone_id;
      if (detectionZoneId && detectionZoneId !== currentZoneId) {
        return; // Detection is for a different zone
      }

      const member = matchDetectionToMember({
        label: payload.label,
        entityId: payload.detection_id,
      });

      if (member) {
        const record: DetectionRecord = {
          memberId: member.id,
          entityId: payload.detection_id,
          timestamp: payload.timestamp || new Date().toISOString(),
          zoneId: currentZoneId,
        };

        setDetectionRecords((prev) => {
          const next = new Map(prev);
          next.set(member.id, record);
          return next;
        });
      }
    },
    [matchDetectionToMember]
  );

  /**
   * Handle event created (security event with zone information).
   */
  const handleEventCreated = useCallback(
    (payload: EventCreatedPayload) => {
      // Events include zone context through their camera
      // Match any person-related event
      const members = householdMembersRef.current;
      if (!members || members.length === 0) return;

      // For security events, we can infer presence from the camera
      // In production, this would be more sophisticated
      const residents = members.filter(
        (m) => m.role === 'resident' || m.role === 'family'
      );

      if (residents.length > 0) {
        const member = residents[0];
        const record: DetectionRecord = {
          memberId: member.id,
          timestamp: payload.started_at || new Date().toISOString(),
          zoneId: zoneIdRef.current,
        };

        setDetectionRecords((prev) => {
          const next = new Map(prev);
          next.set(member.id, record);
          return next;
        });
      }
    },
    []
  );

  // Subscribe to detection and event WebSocket events
  const { isConnected } = useWebSocketEvents(
    {
      [WSEventType.DETECTION_NEW]: handleDetection,
      [WSEventType.EVENT_CREATED]: handleEventCreated,
    },
    { enabled }
  );

  /**
   * Cleanup expired presence records periodically.
   */
  useEffect(() => {
    if (!enabled) return;

    const cleanup = () => {
      const now = Date.now();
      const maxAge = staleThresholdMs * 2; // Keep records for 2x stale threshold

      setDetectionRecords((prev) => {
        let hasChanges = false;
        const next = new Map(prev);

        for (const [memberId, record] of prev.entries()) {
          const recordAge = now - new Date(record.timestamp).getTime();
          if (recordAge > maxAge) {
            next.delete(memberId);
            hasChanges = true;
          }
        }

        return hasChanges ? next : prev;
      });
    };

    const intervalId = setInterval(cleanup, cleanupIntervalMs);
    return () => clearInterval(intervalId);
  }, [enabled, staleThresholdMs, cleanupIntervalMs]);

  /**
   * Clear presence when zone changes.
   */
  useEffect(() => {
    setDetectionRecords(new Map());
  }, [zoneId]);

  /**
   * Clear all presence records manually.
   */
  const clearPresence = useCallback(() => {
    setDetectionRecords(new Map());
  }, []);

  /**
   * Compute presence members from detection records.
   */
  const members = useMemo((): ZonePresenceMember[] => {
    if (!householdMembers) return [];

    const now = Date.now();
    const result: ZonePresenceMember[] = [];

    for (const [memberId, record] of detectionRecords.entries()) {
      const member = householdMembers.find((m) => m.id === memberId);
      if (!member) continue;

      const lastSeenTime = new Date(record.timestamp).getTime();
      const timeSinceDetection = now - lastSeenTime;

      result.push({
        id: member.id,
        name: member.name,
        role: member.role,
        lastSeen: record.timestamp,
        isStale: timeSinceDetection > staleThresholdMs,
        isActive: timeSinceDetection <= activeThresholdMs,
        entityId: record.entityId,
      });
    }

    // Sort by most recently seen
    return result.sort(
      (a, b) => new Date(b.lastSeen).getTime() - new Date(a.lastSeen).getTime()
    );
  }, [householdMembers, detectionRecords, staleThresholdMs, activeThresholdMs]);

  const presentCount = members.length;
  const activeCount = members.filter((m) => m.isActive).length;

  return {
    members,
    isConnected,
    isLoading,
    error,
    presentCount,
    activeCount,
    clearPresence,
  };
}

export default useZonePresence;
