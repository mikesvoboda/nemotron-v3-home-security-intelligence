/**
 * Performance History API Client
 *
 * Provides typed fetch wrappers for historical performance metrics endpoints:
 * - GET /api/system/performance/history - Get performance snapshots over time
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
 * Time range options for historical data.
 */
export type TimeRange = '5m' | '15m' | '60m';

/**
 * GPU metrics within a performance snapshot.
 */
export interface GPUMetrics {
  utilization: number;
  temperature: number;
  vram_used_gb: number;
  vram_total_gb: number;
}

/**
 * Host system metrics within a performance snapshot.
 */
export interface HostMetrics {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
}

/**
 * Database status within a performance snapshot.
 */
export interface DatabaseStatus {
  status: string;
  connections_active?: number;
  connected_clients?: number;
}

/**
 * Alert within a performance snapshot.
 */
export interface PerformanceAlert {
  severity: string;
  metric: string;
  value: number;
  threshold: number;
  message: string;
}

/**
 * A single performance snapshot at a point in time.
 */
export interface PerformanceSnapshot {
  timestamp: string;
  gpu: GPUMetrics | null;
  host: HostMetrics | null;
  databases: Record<string, DatabaseStatus>;
  alerts: PerformanceAlert[];
}

/**
 * Response from performance history endpoint.
 */
export interface PerformanceHistoryResponse {
  snapshots: PerformanceSnapshot[];
  time_range: string;
  count: number;
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Performance History API failures.
 */
export class PerformanceHistoryApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'PerformanceHistoryApiError';
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

    throw new PerformanceHistoryApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new PerformanceHistoryApiError(response.status, 'Failed to parse response JSON', error);
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get performance history data for the specified time range.
 *
 * Fetches historical performance snapshots including GPU, host, and database metrics.
 *
 * @param timeRange - Time range to fetch ('5m', '15m', or '60m')
 * @returns PerformanceHistoryResponse with snapshots and metadata
 * @throws PerformanceHistoryApiError on server errors
 *
 * @example
 * ```typescript
 * const { snapshots, time_range, count } = await getPerformanceHistory('5m');
 * snapshots.forEach(snapshot => {
 *   console.log(`${snapshot.timestamp}: GPU ${snapshot.gpu?.utilization}%`);
 * });
 * ```
 */
export async function getPerformanceHistory(
  timeRange: TimeRange = '5m'
): Promise<PerformanceHistoryResponse> {
  const url = `${BASE_URL}/api/system/performance/history?time_range=${timeRange}`;

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: buildHeaders(),
    });
    return handleResponse<PerformanceHistoryResponse>(response);
  } catch (error) {
    if (error instanceof PerformanceHistoryApiError) {
      throw error;
    }
    throw new PerformanceHistoryApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}
