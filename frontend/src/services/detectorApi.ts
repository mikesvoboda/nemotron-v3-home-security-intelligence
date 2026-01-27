/**
 * Detector API Client
 *
 * Provides typed fetch wrappers for detector management REST endpoints including:
 * - Listing available detectors
 * - Getting active detector
 * - Switching detectors at runtime
 * - Checking detector health
 *
 * @see backend/api/routes/detector.py - Backend implementation
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
 * Information about a registered detector.
 */
export interface DetectorInfo {
  /** Unique identifier (e.g., "yolo26", "yolov8") */
  detector_type: string;
  /** Human-readable name for display */
  display_name: string;
  /** Service URL */
  url: string;
  /** Whether this detector is available for use */
  enabled: boolean;
  /** Whether this is the currently active detector */
  is_active: boolean;
  /** Model version (e.g., "yolo26m", "yolov8n") */
  model_version: string | null;
  /** Description of detector capabilities */
  description: string;
}

/**
 * Health status of a detector.
 */
export interface DetectorHealth {
  /** Detector type identifier */
  detector_type: string;
  /** Whether the detector is healthy */
  healthy: boolean;
  /** Whether the model is loaded */
  model_loaded: boolean;
  /** Health check latency in milliseconds */
  latency_ms: number | null;
  /** Error message if unhealthy */
  error_message: string | null;
}

/**
 * Response from the list detectors endpoint.
 */
export interface DetectorListResponse {
  /** List of all registered detectors */
  detectors: DetectorInfo[];
  /** Currently active detector type */
  active_detector: string | null;
  /** Whether health was checked */
  health_checked: boolean;
}

/**
 * Request to switch the active detector.
 */
export interface SwitchDetectorRequest {
  /** Target detector type */
  detector_type: string;
  /** Skip health check validation */
  force?: boolean;
}

/**
 * Response from switching detectors.
 */
export interface SwitchDetectorResponse {
  /** New active detector type */
  detector_type: string;
  /** Display name */
  display_name: string;
  /** Status message */
  message: string;
  /** Health status of new detector */
  healthy: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Build headers for API requests.
 */
function buildHeaders(): HeadersInit {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response and parse JSON.
 * Throws an error with the response status and message if not ok.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData = (await response.json()) as { detail?: string };
      if (errorData.detail) {
        errorMessage = errorData.detail;
      }
    } catch {
      // Ignore JSON parse errors
    }
    throw new Error(errorMessage);
  }
  return response.json() as Promise<T>;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all registered detectors.
 *
 * @param includeHealth - Whether to include health status (slower)
 * @returns List of detectors with configuration
 */
export async function listDetectors(
  includeHealth: boolean = false
): Promise<DetectorListResponse> {
  const url = new URL(`${BASE_URL}/api/system/detectors`);
  if (includeHealth) {
    url.searchParams.set('include_health', 'true');
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: buildHeaders(),
  });

  return handleResponse<DetectorListResponse>(response);
}

/**
 * Get the currently active detector.
 *
 * @returns Active detector configuration
 */
export async function getActiveDetector(): Promise<DetectorInfo> {
  const response = await fetch(`${BASE_URL}/api/system/detectors/active`, {
    method: 'GET',
    headers: buildHeaders(),
  });

  return handleResponse<DetectorInfo>(response);
}

/**
 * Switch to a different detector.
 *
 * @param request - Switch request with target detector type
 * @returns Result of the switch operation
 */
export async function switchDetector(
  request: SwitchDetectorRequest
): Promise<SwitchDetectorResponse> {
  const response = await fetch(`${BASE_URL}/api/system/detectors/active`, {
    method: 'PUT',
    headers: buildHeaders(),
    body: JSON.stringify(request),
  });

  return handleResponse<SwitchDetectorResponse>(response);
}

/**
 * Get configuration for a specific detector.
 *
 * @param detectorType - Detector type identifier
 * @returns Detector configuration
 */
export async function getDetectorConfig(
  detectorType: string
): Promise<DetectorInfo> {
  const response = await fetch(
    `${BASE_URL}/api/system/detectors/${encodeURIComponent(detectorType)}`,
    {
      method: 'GET',
      headers: buildHeaders(),
    }
  );

  return handleResponse<DetectorInfo>(response);
}

/**
 * Check health of a specific detector.
 *
 * @param detectorType - Detector type identifier
 * @returns Health status
 */
export async function checkDetectorHealth(
  detectorType: string
): Promise<DetectorHealth> {
  const response = await fetch(
    `${BASE_URL}/api/system/detectors/${encodeURIComponent(detectorType)}/health`,
    {
      method: 'GET',
      headers: buildHeaders(),
    }
  );

  return handleResponse<DetectorHealth>(response);
}
