/**
 * Baseline Configuration API Client
 *
 * Provides typed fetch wrappers for camera baseline configuration REST endpoints:
 * - Get baseline configuration for a camera
 * - Update per-camera baseline settings
 * - Reset baseline data for a camera
 *
 * @see backend/api/routes/cameras.py - Backend implementation
 * @see NEM-4921 - Phase 3: Baseline Tuning UI
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
 * Global baseline configuration settings.
 * These are the default values used when per-camera override is disabled.
 */
export interface GlobalBaselineConfig {
  /** Threshold in standard deviations for anomaly detection */
  threshold_stdev: number;
  /** Minimum samples required before anomaly detection is reliable */
  min_samples: number;
  /** Exponential decay factor for EWMA calculations */
  decay_factor: number;
  /** Rolling window size in days for baseline calculations */
  window_days: number;
}

/**
 * Baseline configuration response for a camera.
 * Includes both active settings and global defaults for reference.
 */
export interface BaselineConfigResponse {
  /** Active threshold for anomaly detection (per-camera or global) */
  threshold_stdev: number;
  /** Active minimum samples requirement (per-camera or global) */
  min_samples: number;
  /** Whether per-camera overrides are active */
  override_global_config: boolean;
  /** Global configuration defaults for reference */
  global_config: GlobalBaselineConfig;
}

/**
 * Request body for updating baseline configuration.
 * All fields are optional - only specified fields are updated.
 */
export interface BaselineConfigUpdate {
  /** New threshold in standard deviations (0.5-5.0) */
  threshold_stdev?: number;
  /** New minimum samples requirement (>= 1) */
  min_samples?: number;
  /** Whether to enable per-camera overrides */
  override_global_config?: boolean;
}

/**
 * Response from baseline reset operation.
 */
export interface BaselineResetResponse {
  /** Number of ActivityBaseline records deleted */
  activity_baselines_deleted: number;
  /** Number of ClassBaseline records deleted */
  class_baselines_deleted: number;
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Baseline Configuration API failures.
 * Includes HTTP status code and parsed error data.
 */
export class BaselineConfigApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'BaselineConfigApiError';
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
 * Parses error details from FastAPI response format.
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

    throw new BaselineConfigApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new BaselineConfigApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the Baseline Config API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/cameras)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchBaselineConfigApiInner<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}/api/cameras${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof BaselineConfigApiError) {
      throw error;
    }
    throw new BaselineConfigApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get baseline configuration for a camera.
 *
 * Returns the active configuration for anomaly detection, including both
 * per-camera overrides (if enabled) and global defaults.
 *
 * @param cameraId - ID of the camera
 * @returns BaselineConfigResponse containing active config and global defaults
 * @throws BaselineConfigApiError on server errors or if camera not found
 *
 * @example
 * ```typescript
 * const config = await fetchBaselineConfig('front_door');
 * if (config.override_global_config) {
 *   console.log('Using custom settings:', config.threshold_stdev);
 * } else {
 *   console.log('Using global defaults');
 * }
 * ```
 */
export async function fetchBaselineConfig(cameraId: string): Promise<BaselineConfigResponse> {
  return fetchBaselineConfigApiInner<BaselineConfigResponse>(
    `/${encodeURIComponent(cameraId)}/baseline/config`
  );
}

/**
 * Update baseline configuration for a camera.
 *
 * Updates per-camera configuration overrides for anomaly detection.
 * If override_global_config is set to False, per-camera values are
 * ignored in favor of global defaults.
 *
 * @param cameraId - ID of the camera
 * @param config - Configuration update payload
 * @returns Updated BaselineConfigResponse
 * @throws BaselineConfigApiError on validation errors or if camera not found
 *
 * @example
 * ```typescript
 * // Enable per-camera override with custom settings
 * const updated = await updateBaselineConfig('front_door', {
 *   threshold_stdev: 3.0,
 *   min_samples: 15,
 *   override_global_config: true,
 * });
 *
 * // Revert to global settings
 * const reverted = await updateBaselineConfig('front_door', {
 *   override_global_config: false,
 * });
 * ```
 */
export async function updateBaselineConfig(
  cameraId: string,
  config: BaselineConfigUpdate
): Promise<BaselineConfigResponse> {
  return fetchBaselineConfigApiInner<BaselineConfigResponse>(
    `/${encodeURIComponent(cameraId)}/baseline/config`,
    {
      method: 'PUT',
      body: JSON.stringify(config),
    }
  );
}

/**
 * Reset all baseline data for a camera.
 *
 * Deletes all ActivityBaseline and ClassBaseline records for the camera.
 * This forces the baseline to be re-learned from new detections.
 *
 * @param cameraId - ID of the camera
 * @returns BaselineResetResponse with counts of deleted records
 * @throws BaselineConfigApiError on server errors or if camera not found
 *
 * @example
 * ```typescript
 * const result = await resetCameraBaseline('front_door');
 * console.log(`Deleted ${result.activity_baselines_deleted} activity baselines`);
 * console.log(`Deleted ${result.class_baselines_deleted} class baselines`);
 * ```
 */
export async function resetCameraBaseline(cameraId: string): Promise<BaselineResetResponse> {
  return fetchBaselineConfigApiInner<BaselineResetResponse>(
    `/${encodeURIComponent(cameraId)}/baseline/reset`,
    {
      method: 'POST',
    }
  );
}
