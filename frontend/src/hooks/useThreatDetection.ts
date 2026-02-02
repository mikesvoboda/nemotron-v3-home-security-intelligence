/**
 * useThreatDetection - Hook for managing weapon/threat detection state
 *
 * Tracks active threat detections, provides summary information, and handles
 * threat expiration and dismissal. Integrates with WebSocket events to receive
 * real-time threat notifications.
 *
 * NEM-5024: Phase 4 - Threat Detection Surfacing
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { threatSummary, addThreat, dismissThreat } = useThreatDetection();
 *
 *   return (
 *     <ThreatDetectionBanner
 *       threatSummary={threatSummary}
 *       onDismiss={() => threatSummary.latestThreat && dismissThreat(threatSummary.latestThreat.id!)}
 *     />
 *   );
 * }
 * ```
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';

import {
  createThreatSummary,
  createEmptyThreatSummary,
  type ThreatDetection,
  type ThreatSummary,
} from '../types/threat';

// ============================================================================
// Types
// ============================================================================

export interface UseThreatDetectionOptions {
  /**
   * Time in milliseconds before a threat expires and is automatically removed.
   * Set to 0 to disable expiration.
   * Default: 5 minutes (300000ms)
   */
  expirationMs?: number;

  /**
   * Maximum number of threats to track.
   * Oldest threats are removed when limit is exceeded.
   * Default: 50
   */
  maxThreats?: number;
}

export interface UseThreatDetectionReturn {
  /** Summary of all active (non-dismissed) threats */
  threatSummary: ThreatSummary;

  /** Whether the hook is loading initial threat data */
  isLoading: boolean;

  /** List of dismissed threat IDs */
  dismissedIds: Set<number>;

  /** Add a new threat detection */
  addThreat: (threat: ThreatDetection) => void;

  /** Remove a specific threat by ID */
  removeThreat: (threatId: number) => void;

  /** Clear all active threats */
  clearThreats: () => void;

  /** Dismiss a threat (prevents it from being shown again) */
  dismissThreat: (threatId: number) => void;

  /** Clear all dismissed threat IDs */
  clearDismissed: () => void;
}

// ============================================================================
// Internal Types
// ============================================================================

interface TrackedThreat extends ThreatDetection {
  /** Internal timestamp for expiration tracking */
  _addedAt: number;
}

// ============================================================================
// Hook Implementation
// ============================================================================

const DEFAULT_EXPIRATION_MS = 5 * 60 * 1000; // 5 minutes
const DEFAULT_MAX_THREATS = 50;

export function useThreatDetection(
  options: UseThreatDetectionOptions = {}
): UseThreatDetectionReturn {
  const {
    expirationMs = DEFAULT_EXPIRATION_MS,
    maxThreats = DEFAULT_MAX_THREATS,
  } = options;

  // State for active threats
  const [threats, setThreats] = useState<TrackedThreat[]>([]);

  // Set of dismissed threat IDs
  const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set());

  // Ref to always have access to current dismissed IDs (for avoiding stale closures)
  const dismissedIdsRef = useRef<Set<number>>(dismissedIds);
  dismissedIdsRef.current = dismissedIds;

  // Loading state (for future API integration)
  const [isLoading] = useState(false);

  // Ref to track expiration timer
  const expirationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Add a new threat
  const addThreat = useCallback((threat: ThreatDetection) => {
    // Don't add if already dismissed (use ref to avoid stale closure)
    if (threat.id !== undefined && dismissedIdsRef.current.has(threat.id)) {
      return;
    }

    setThreats((prev) => {
      // Check for duplicates by ID
      if (threat.id !== undefined) {
        const exists = prev.some((t) => t.id === threat.id);
        if (exists) {
          // Update existing threat
          return prev.map((t) =>
            t.id === threat.id
              ? { ...threat, _addedAt: Date.now() }
              : t
          );
        }
      }

      // Add new threat
      const newThreat: TrackedThreat = {
        ...threat,
        _addedAt: Date.now(),
      };

      // Maintain max threats limit
      const updated = [newThreat, ...prev];
      if (updated.length > maxThreats) {
        return updated.slice(0, maxThreats);
      }

      return updated;
    });
  }, [maxThreats]);

  // Remove a specific threat by ID
  const removeThreat = useCallback((threatId: number) => {
    setThreats((prev) => prev.filter((t) => t.id !== threatId));
  }, []);

  // Clear all threats
  const clearThreats = useCallback(() => {
    setThreats([]);
  }, []);

  // Dismiss a threat (removes it and prevents re-adding)
  const dismissThreat = useCallback((threatId: number) => {
    setDismissedIds((prev) => {
      const next = new Set(prev);
      next.add(threatId);
      return next;
    });
    removeThreat(threatId);
  }, [removeThreat]);

  // Clear dismissed IDs
  const clearDismissed = useCallback(() => {
    setDismissedIds(new Set());
  }, []);

  // Handle threat expiration
  useEffect(() => {
    // Don't set up expiration if disabled
    if (expirationMs <= 0) {
      return;
    }

    // Check for expired threats every second
    const checkExpiration = () => {
      const now = Date.now();
      setThreats((prev) => {
        const filtered = prev.filter((t) => now - t._addedAt < expirationMs);
        // Only update if something changed
        if (filtered.length === prev.length) {
          return prev;
        }
        return filtered;
      });
    };

    expirationTimerRef.current = setInterval(checkExpiration, 1000);

    return () => {
      if (expirationTimerRef.current) {
        clearInterval(expirationTimerRef.current);
        expirationTimerRef.current = null;
      }
    };
  }, [expirationMs]);

  // Compute threat summary from active threats
  const threatSummary = useMemo<ThreatSummary>(() => {
    if (threats.length === 0) {
      return createEmptyThreatSummary();
    }

    // Strip internal tracking fields for the summary
    const cleanThreats: ThreatDetection[] = threats.map(

      ({ _addedAt, ...threat }) => threat
    );

    return createThreatSummary(cleanThreats);
  }, [threats]);

  return {
    threatSummary,
    isLoading,
    dismissedIds,
    addThreat,
    removeThreat,
    clearThreats,
    dismissThreat,
    clearDismissed,
  };
}
