/**
 * useEnrichmentProgress - Hook for tracking enrichment progress by event/batch
 *
 * Provides a convenient way to get enrichment status for specific events
 * by wrapping useEventEnrichmentWebSocket and indexing by event ID.
 *
 * This hook is designed for integration with EventCard and EventTimeline
 * to show real-time enrichment progress indicators.
 *
 * @module hooks/useEnrichmentProgress
 */

import { useCallback, useMemo } from 'react';

import {
  useEventEnrichmentWebSocket,
  type ActiveEnrichment,
  type EnrichmentHistoryEntry,
  type UseEventEnrichmentWebSocketOptions,
} from './useEventEnrichmentWebSocket';

import type { EnrichmentProgressStatus } from '../components/events/EnrichmentProgressBadge';

// ============================================================================
// Types
// ============================================================================

/**
 * Enrichment progress state for a specific event
 */
export interface EventEnrichmentProgress {
  /** Current enrichment status */
  status: EnrichmentProgressStatus;
  /** Progress percentage (0-100) when in progress */
  progress?: number;
  /** Current processing stage name */
  stage?: string;
  /** Error message when status is failed */
  error?: string;
  /** Total number of enrichment steps */
  totalSteps?: number;
  /** Current step number */
  currentStep?: number;
  /** Whether there is active enrichment data */
  hasData: boolean;
}

/**
 * Options for the useEnrichmentProgress hook
 */
export interface UseEnrichmentProgressOptions extends UseEventEnrichmentWebSocketOptions {
  /**
   * Map of event IDs to batch IDs for looking up enrichment by event
   * This is typically provided by the parent component that knows
   * which events are currently being processed.
   */
  eventBatchMap?: Map<number, string>;
}

/**
 * Return type for the useEnrichmentProgress hook
 */
export interface UseEnrichmentProgressReturn {
  /**
   * Get enrichment progress for a specific event ID
   * Returns null if no enrichment data is available for the event
   */
  getProgressForEvent: (eventId: number) => EventEnrichmentProgress | null;

  /**
   * Get enrichment progress for a specific batch ID
   */
  getProgressForBatch: (batchId: string) => EventEnrichmentProgress | null;

  /** Currently active enrichments */
  activeEnrichments: ActiveEnrichment[];

  /** Completed/failed enrichment history */
  history: EnrichmentHistoryEntry[];

  /** Total completed enrichments */
  completedCount: number;

  /** Total failed enrichments */
  failedCount: number;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Whether any enrichments are currently in progress */
  hasActiveEnrichments: boolean;

  /** Register an event ID to batch ID mapping */
  registerEventBatch: (eventId: number, batchId: string) => void;

  /** Clear the history buffer */
  clearHistory: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Convert an active enrichment to progress state
 */
function activeToProgress(active: ActiveEnrichment): EventEnrichmentProgress {
  return {
    status: 'in_progress',
    progress: active.progress,
    stage: active.current_step,
    totalSteps: active.total_steps,
    hasData: true,
  };
}

/**
 * Convert a history entry to progress state
 */
function historyToProgress(entry: EnrichmentHistoryEntry): EventEnrichmentProgress {
  if (entry.status === 'error') {
    return {
      status: 'failed',
      error: entry.error,
      hasData: true,
    };
  }

  return {
    status: 'completed',
    hasData: true,
  };
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to track enrichment progress with convenient event-based lookup
 *
 * @example
 * ```tsx
 * // In a parent component (e.g., EventTimeline)
 * const {
 *   getProgressForBatch,
 *   activeEnrichments,
 *   hasActiveEnrichments,
 * } = useEnrichmentProgress({ enabled: true });
 *
 * // In EventCard or child component
 * const progress = getProgressForBatch(event.batch_id);
 * if (progress) {
 *   return (
 *     <EnrichmentProgressBadge
 *       status={progress.status}
 *       progress={progress.progress}
 *       stage={progress.stage}
 *       error={progress.error}
 *     />
 *   );
 * }
 * ```
 */
export function useEnrichmentProgress(
  options: UseEnrichmentProgressOptions = {}
): UseEnrichmentProgressReturn {
  const { eventBatchMap = new Map<number, string>(), ...wsOptions } = options;

  // Use the base WebSocket hook
  const {
    activeEnrichments,
    history,
    completedCount,
    failedCount,
    isConnected,
    clearHistory,
  } = useEventEnrichmentWebSocket(wsOptions);

  // Create lookup maps for efficient access
  const activeByBatchId = useMemo(() => {
    const map = new Map<string, ActiveEnrichment>();
    for (const active of activeEnrichments) {
      map.set(active.batch_id, active);
    }
    return map;
  }, [activeEnrichments]);

  const historyByBatchId = useMemo(() => {
    const map = new Map<string, EnrichmentHistoryEntry>();
    for (const entry of history) {
      // Only keep the most recent entry for each batch
      if (!map.has(entry.batch_id)) {
        map.set(entry.batch_id, entry);
      }
    }
    return map;
  }, [history]);

  // Get progress for a specific batch ID
  const getProgressForBatch = useCallback(
    (batchId: string): EventEnrichmentProgress | null => {
      // Check active enrichments first
      const active = activeByBatchId.get(batchId);
      if (active) {
        return activeToProgress(active);
      }

      // Check history (completed or failed)
      const historyEntry = historyByBatchId.get(batchId);
      if (historyEntry) {
        return historyToProgress(historyEntry);
      }

      return null;
    },
    [activeByBatchId, historyByBatchId]
  );

  // Get progress for a specific event ID (using event-batch mapping)
  const getProgressForEvent = useCallback(
    (eventId: number): EventEnrichmentProgress | null => {
      const batchId = eventBatchMap.get(eventId);
      if (!batchId) {
        return null;
      }
      return getProgressForBatch(batchId);
    },
    [eventBatchMap, getProgressForBatch]
  );

  // Register event to batch mapping (no-op in this implementation,
  // the mapping should be managed by the parent component)
  const registerEventBatch = useCallback((_eventId: number, _batchId: string) => {
    // This is a no-op since the map is passed in via options
    // In a more complex implementation, this could update internal state
  }, []);

  const hasActiveEnrichments = activeEnrichments.length > 0;

  return {
    getProgressForEvent,
    getProgressForBatch,
    activeEnrichments,
    history,
    completedCount,
    failedCount,
    isConnected,
    hasActiveEnrichments,
    registerEventBatch,
    clearHistory,
  };
}

export default useEnrichmentProgress;
