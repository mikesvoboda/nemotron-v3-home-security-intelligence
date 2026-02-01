/**
 * Pipeline Latency History API Client
 *
 * Provides typed fetch wrappers for pipeline latency history REST endpoints including:
 * - GET /api/system/pipeline-latency/history - Fetch historical pipeline latency metrics
 *
 * @see backend/api/routes/performance.py - Backend implementation
 */

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

// ============================================================================
// Types
// ============================================================================

/**
 * Latency metrics for a single pipeline stage.
 */
export interface StageLatency {
  /** Average latency in milliseconds */
  avg_ms: number;
  /** 50th percentile latency in milliseconds */
  p50_ms: number;
  /** 95th percentile latency in milliseconds */
  p95_ms: number;
  /** 99th percentile latency in milliseconds */
  p99_ms: number;
  /** Number of samples in this bucket */
  sample_count: number;
}

/**
 * Pipeline stages with their latency metrics.
 */
export interface PipelineStages {
  /** Latency from file watch to detection start */
  watch_to_detect?: StageLatency;
  /** Latency from detection complete to batch start */
  detect_to_batch?: StageLatency;
  /** Latency from batch complete to analysis start */
  batch_to_analyze?: StageLatency;
  /** Total end-to-end pipeline latency */
  total_pipeline?: StageLatency;
}

/**
 * A single snapshot of pipeline latency metrics at a point in time.
 */
export interface PipelineLatencySnapshot {
  /** Timestamp of the snapshot (ISO 8601) */
  timestamp: string;
  /** Latency metrics for each pipeline stage */
  stages: PipelineStages;
}

/**
 * Response from pipeline latency history endpoint.
 */
export interface PipelineLatencyHistoryResponse {
  /** Array of latency snapshots */
  snapshots: PipelineLatencySnapshot[];
  /** Time window in minutes */
  window_minutes: number;
  /** Bucket size in seconds */
  bucket_seconds: number;
  /** Timestamp when the response was generated */
  timestamp: string;
}

/**
 * Parameters for fetching pipeline latency history.
 */
export interface PipelineLatencyHistoryParams {
  /** Time window in minutes (how far back to look) */
  since?: number;
  /** Bucket size in seconds (aggregation granularity) */
  bucket_seconds?: number;
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Pipeline Latency API failures.
 */
export class PipelineLatencyApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'PipelineLatencyApiError';
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Build headers with optional API key authentication.
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response with proper error handling.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorData: unknown = undefined;

    try {
      const errorBody: unknown = await response.json();
      if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
        errorMessage = String((errorBody as { detail: unknown }).detail);
        errorData = errorBody;
      } else if (typeof errorBody === 'string') {
        errorMessage = errorBody;
      } else {
        errorData = errorBody;
      }
    } catch {
      // If response body is not JSON, use status text
    }

    throw new PipelineLatencyApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new PipelineLatencyApiError(response.status, 'Failed to parse response JSON', error);
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get pipeline latency history data.
 *
 * Fetches historical pipeline latency metrics aggregated into time buckets.
 *
 * @param params - Query parameters for the request
 * @param params.since - Time window in minutes (default: 60)
 * @param params.bucket_seconds - Bucket size in seconds (default: 60)
 * @returns PipelineLatencyHistoryResponse with snapshots and metadata
 * @throws PipelineLatencyApiError on server errors
 *
 * @example
 * ```typescript
 * const { snapshots, window_minutes, bucket_seconds } = await getPipelineLatencyHistory({
 *   since: 60,
 *   bucket_seconds: 60,
 * });
 * snapshots.forEach(snapshot => {
 *   console.log(`${snapshot.timestamp}: ${snapshot.stages.total_pipeline?.avg_ms}ms avg`);
 * });
 * ```
 */
export async function getPipelineLatencyHistory(
  params: PipelineLatencyHistoryParams = {}
): Promise<PipelineLatencyHistoryResponse> {
  const { since = 60, bucket_seconds = 60 } = params;

  const queryParams = new URLSearchParams();
  queryParams.append('since', since.toString());
  queryParams.append('bucket_seconds', bucket_seconds.toString());

  const url = `${BASE_URL}/api/system/pipeline-latency/history?${queryParams.toString()}`;

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: buildHeaders(),
    });
    return handleResponse<PipelineLatencyHistoryResponse>(response);
  } catch (error) {
    if (error instanceof PipelineLatencyApiError) {
      throw error;
    }
    throw new PipelineLatencyApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}
