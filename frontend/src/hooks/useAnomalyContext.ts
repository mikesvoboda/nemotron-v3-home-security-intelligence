/**
 * useAnomalyContext - Hook for fetching anomaly investigation context (NEM-4714)
 *
 * Provides detailed context for investigating a zone anomaly, including
 * associated detections and acknowledgment status.
 *
 * Part of Phase 3B: Anomaly Investigation Features.
 *
 * @module hooks/useAnomalyContext
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// ============================================================================
// Types
// ============================================================================

/**
 * Detection associated with an anomaly.
 */
export interface AssociatedDetection {
  /** Detection ID */
  id: string;
  /** Camera ID where detected */
  camera_id: string;
  /** When the detection occurred */
  timestamp: string;
  /** Object class (e.g., 'person', 'vehicle') */
  object_class: string;
  /** Detection confidence score (0-1) */
  confidence: number;
  /** Risk score assigned by AI (0-100) */
  risk_score: number | null;
  /** Thumbnail URL for visual context */
  thumbnail_url: string | null;
}

/**
 * Full context for an anomaly investigation.
 */
export interface AnomalyContext {
  /** Anomaly ID */
  id: string;
  /** Zone ID where anomaly occurred */
  zone_id: number;
  /** Zone name for display */
  zone_name: string;
  /** Type of anomaly */
  anomaly_type: string;
  /** Severity level */
  severity: string;
  /** When the anomaly occurred */
  timestamp: string;
  /** Expected value from baseline */
  expected_value: number | null;
  /** Actual observed value */
  actual_value: number | null;
  /** AI-generated explanation */
  explanation: string | null;
  /** Associated detections */
  detections: AssociatedDetection[];
  /** Whether the anomaly has been acknowledged */
  acknowledged: boolean;
  /** When the anomaly was acknowledged */
  acknowledged_at: string | null;
}

/**
 * Options for the useAnomalyContext hook.
 */
export interface UseAnomalyContextOptions {
  /** Whether the query is enabled */
  enabled?: boolean;
}

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = '/api/zones';

/**
 * Fetch detailed context for an anomaly.
 */
async function fetchAnomalyContext(anomalyId: string): Promise<AnomalyContext> {
  const response = await fetch(`${API_BASE}/anomalies/${anomalyId}/context`);
  if (!response.ok) {
    throw new Error(`Failed to fetch anomaly context: ${response.statusText}`);
  }
  return response.json() as Promise<AnomalyContext>;
}

/**
 * Acknowledge an anomaly.
 */
async function acknowledgeAnomaly(anomalyId: string): Promise<{ acknowledged: boolean; acknowledged_at: string }> {
  const response = await fetch(`${API_BASE}/anomalies/${anomalyId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to acknowledge anomaly: ${response.statusText}`);
  }
  return response.json() as Promise<{ acknowledged: boolean; acknowledged_at: string }>;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook for fetching anomaly investigation context.
 *
 * Fetches detailed context for investigating a zone anomaly, including
 * associated detections and provides acknowledgment functionality.
 *
 * @param anomalyId - The ID of the anomaly to investigate
 * @param options - Hook options
 * @returns Query result with anomaly context and acknowledge mutation
 *
 * @example
 * ```tsx
 * const {
 *   data,
 *   isLoading,
 *   error,
 *   acknowledgeAnomaly,
 *   isAcknowledging,
 * } = useAnomalyContext(selectedAnomalyId, { enabled: !!selectedAnomalyId });
 *
 * if (data) {
 *   console.log(`Zone: ${data.zone_name}, Detections: ${data.detections.length}`);
 * }
 * ```
 */
export function useAnomalyContext(
  anomalyId: string | null,
  options: UseAnomalyContextOptions = {}
) {
  const { enabled = true } = options;
  const queryClient = useQueryClient();

  // Query for fetching anomaly context
  const query = useQuery({
    queryKey: ['anomaly-context', anomalyId],
    queryFn: () => {
      if (!anomalyId) throw new Error('Anomaly ID is required');
      return fetchAnomalyContext(anomalyId);
    },
    enabled: enabled && !!anomalyId,
    staleTime: 30000, // 30 seconds
  });

  // Mutation for acknowledging the anomaly
  const acknowledgeMutation = useMutation({
    mutationFn: () => {
      if (!anomalyId) throw new Error('Anomaly ID is required');
      return acknowledgeAnomaly(anomalyId);
    },
    onSuccess: (data) => {
      // Update the cache with the new acknowledged state
      queryClient.setQueryData<AnomalyContext>(['anomaly-context', anomalyId], (old) => {
        if (!old) return old;
        return {
          ...old,
          acknowledged: data.acknowledged,
          acknowledged_at: data.acknowledged_at,
        };
      });
      // Invalidate the anomaly lists to reflect the change
      void queryClient.invalidateQueries({ queryKey: ['zone-anomalies'] });
    },
  });

  return {
    /** Anomaly context data */
    data: query.data,
    /** Whether the initial fetch is in progress */
    isLoading: query.isLoading,
    /** Whether any fetch is in progress */
    isFetching: query.isFetching,
    /** Error object if the query failed */
    error: query.error,
    /** Whether the query has errored */
    isError: query.isError,
    /** Function to manually trigger a refetch */
    refetch: query.refetch,
    /** Function to acknowledge the anomaly */
    acknowledgeAnomaly: acknowledgeMutation.mutate,
    /** Whether acknowledge mutation is in progress */
    isAcknowledging: acknowledgeMutation.isPending,
    /** Error from acknowledge mutation */
    acknowledgeError: acknowledgeMutation.error,
  };
}

export default useAnomalyContext;
