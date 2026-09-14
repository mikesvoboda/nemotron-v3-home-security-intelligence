/**
 * GPU History API Client
 *
 * Provides typed fetch wrappers for GPU history REST endpoints including:
 * - GET /api/system/gpu/history - Fetch historical GPU metrics
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
 * Individual GPU history record with metrics at a specific point in time.
 */
export interface GPUHistoryItem {
  /** Timestamp when the metrics were recorded (ISO 8601) */
  recorded_at: string;
  /** GPU model name */
  gpu_name: string;
  /** GPU utilization percentage (0-100) */
  utilization: number;
  /** Memory used in MB */
  memory_used: number;
  /** Total memory in MB */
  memory_total: number;
  /** GPU temperature in Celsius */
  temperature: number;
  /** Power usage in watts */
  power_usage: number;
  /** Inference frames per second */
  inference_fps: number;
}

/**
 * Pagination metadata for GPU history response.
 */
export interface GPUHistoryPagination {
  /** Total number of records available */
  total: number;
  /** Number of records returned per page */
  limit: number;
  /** Whether more records are available */
  has_more: boolean;
}

/**
 * Response from GPU history endpoint.
 */
export interface GPUHistoryResponse {
  /** Array of GPU history items */
  items: GPUHistoryItem[];
  /** Pagination metadata */
  pagination: GPUHistoryPagination;
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for GPU History API failures.
 */
export class GPUHistoryApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'GPUHistoryApiError';
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

    throw new GPUHistoryApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new GPUHistoryApiError(response.status, 'Failed to parse response JSON', error);
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get GPU history data.
 *
 * Fetches historical GPU metrics with pagination support.
 *
 * @param limit - Maximum number of records to return (default: 300)
 * @returns GPUHistoryResponse with items and pagination
 * @throws GPUHistoryApiError on server errors
 *
 * @example
 * ```typescript
 * const { items, pagination } = await getGPUHistory(300);
 * items.forEach(item => {
 *   console.log(`${item.recorded_at}: ${item.utilization}% utilization`);
 * });
 * ```
 */
export async function getGPUHistory(limit: number = 300): Promise<GPUHistoryResponse> {
  const url = `${BASE_URL}/api/system/gpu/history?limit=${limit}`;

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: buildHeaders(),
    });
    return handleResponse<GPUHistoryResponse>(response);
  } catch (error) {
    if (error instanceof GPUHistoryApiError) {
      throw error;
    }
    throw new GPUHistoryApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}
