/**
 * API Client for Home Security Dashboard
 * Provides typed fetch wrappers for all REST endpoints
 *
 * Types are now generated from the backend OpenAPI specification.
 * Run `./scripts/generate-types.sh` to regenerate types after backend changes.
 *
 * @see frontend/src/types/generated/ - Auto-generated OpenAPI types
 */

// ============================================================================
// Re-export generated types for backward compatibility
// These types are generated from backend/api/schemas/*.py via OpenAPI
// ============================================================================

export type {
  Camera,
  CameraCreate,
  CameraUpdate,
  CameraListResponse,
  Event,
  EventListResponse,
  EventStatsResponse,
  Detection,
  DetectionListResponse,
  HealthResponse,
  ServiceStatus,
  GPUStats,
  GPUStatsSample,
  GPUStatsHistoryResponse,
  SystemConfig,
  SystemConfigUpdate,
  SystemStats,
  LivenessResponse,
  ReadinessResponse,
  WorkerStatus,
  TelemetryResponse,
  QueueDepths,
  PipelineLatencies,
  StageLatency,
  LogEntry,
  LogsResponse,
  LogStats,
  FrontendLogCreate,
  DLQJobResponse,
  DLQJobsResponse,
  DLQStatsResponse,
  DLQClearResponse,
  DLQRequeueResponse,
  DLQName,
  MediaErrorResponse,
  CleanupResponse,
  HTTPValidationError,
  ValidationError,
} from '../types/generated';

// Import concrete types for use in this module
import type {
  Camera,
  CameraCreate,
  CameraUpdate,
  CameraListResponse as GeneratedCameraListResponse,
  Event,
  EventListResponse as GeneratedEventListResponse,
  DetectionListResponse as GeneratedDetectionListResponse,
  HealthResponse,
  GPUStats,
  SystemConfig,
  SystemConfigUpdate,
  SystemStats,
  LogsResponse as GeneratedLogsResponse,
  LogStats,
  CleanupResponse,
} from '../types/generated';

// ============================================================================
// Additional types not in OpenAPI (client-side only)
// ============================================================================

export interface EventsQueryParams {
  camera_id?: string;
  risk_level?: string;
  start_date?: string;
  end_date?: string;
  reviewed?: boolean;
  object_type?: string;
  limit?: number;
  offset?: number;
}

// ============================================================================
// Error Handling
// ============================================================================

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL as string | undefined;

// ============================================================================
// WebSocket URL Helper
// ============================================================================

/**
 * Internal function for building WebSocket URLs. Exported for testing.
 * @internal
 */
export function buildWebSocketUrlInternal(
  endpoint: string,
  wsBaseUrl: string | undefined,
  apiKey: string | undefined,
  windowLocation: { protocol: string; host: string } | undefined
): string {
  let wsUrl: string;

  if (wsBaseUrl) {
    // Use configured WS base URL
    wsUrl = wsBaseUrl.replace(/\/$/, '') + endpoint;
  } else {
    // Fall back to window.location.host
    const protocol = windowLocation?.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = windowLocation?.host || 'localhost:8000';
    wsUrl = `${protocol}//${host}${endpoint}`;
  }

  // Append API key if configured
  if (apiKey) {
    const separator = wsUrl.includes('?') ? '&' : '?';
    wsUrl = `${wsUrl}${separator}api_key=${encodeURIComponent(apiKey)}`;
  }

  return wsUrl;
}

/**
 * Constructs a WebSocket URL for the given endpoint.
 * Uses VITE_WS_BASE_URL if set, otherwise falls back to window.location.host.
 * Appends api_key query parameter if VITE_API_KEY is set.
 *
 * @param endpoint - The WebSocket endpoint path (e.g., '/ws/events')
 * @returns The full WebSocket URL with optional api_key query parameter
 */
export function buildWebSocketUrl(endpoint: string): string {
  const windowLocation =
    typeof window !== 'undefined'
      ? { protocol: window.location.protocol, host: window.location.host }
      : undefined;
  return buildWebSocketUrlInternal(endpoint, WS_BASE_URL, API_KEY, windowLocation);
}

/**
 * Returns the API key if configured, otherwise undefined.
 * Useful for components that need to check if API key auth is enabled.
 */
export function getApiKey(): string | undefined {
  return API_KEY;
}

// ============================================================================
// Helper Functions
// ============================================================================

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

    throw new ApiError(response.status, errorMessage, errorData);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ApiError(response.status, 'Failed to parse response JSON', error);
  }
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;

  // Build headers with optional API key
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options?.headers,
  };

  // Add API key header if configured
  if (API_KEY) {
    (headers as Record<string, string>)['X-API-Key'] = API_KEY;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    // Network or other errors
    throw new ApiError(0, error instanceof Error ? error.message : 'Network request failed');
  }
}

// ============================================================================
// Camera Endpoints
// ============================================================================

export async function fetchCameras(): Promise<Camera[]> {
  const response = await fetchApi<GeneratedCameraListResponse>('/api/cameras');
  return response.cameras;
}

export async function fetchCamera(id: string): Promise<Camera> {
  return fetchApi<Camera>(`/api/cameras/${id}`);
}

export async function createCamera(data: CameraCreate): Promise<Camera> {
  return fetchApi<Camera>('/api/cameras', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateCamera(id: string, data: CameraUpdate): Promise<Camera> {
  return fetchApi<Camera>(`/api/cameras/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteCamera(id: string): Promise<void> {
  return fetchApi<void>(`/api/cameras/${id}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// System Endpoints
// ============================================================================

export async function fetchHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>('/api/system/health');
}

export async function fetchGPUStats(): Promise<GPUStats> {
  return fetchApi<GPUStats>('/api/system/gpu');
}

export async function fetchConfig(): Promise<SystemConfig> {
  return fetchApi<SystemConfig>('/api/system/config');
}

export async function updateConfig(data: SystemConfigUpdate): Promise<SystemConfig> {
  return fetchApi<SystemConfig>('/api/system/config', {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function fetchStats(): Promise<SystemStats> {
  return fetchApi<SystemStats>('/api/system/stats');
}

export async function triggerCleanup(): Promise<CleanupResponse> {
  return fetchApi<CleanupResponse>('/api/system/cleanup', {
    method: 'POST',
  });
}

// ============================================================================
// Event Endpoints
// ============================================================================

export async function fetchEvents(params?: EventsQueryParams): Promise<GeneratedEventListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
    if (params.risk_level) queryParams.append('risk_level', params.risk_level);
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.reviewed !== undefined) queryParams.append('reviewed', String(params.reviewed));
    if (params.object_type) queryParams.append('object_type', params.object_type);
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/events?${queryString}` : '/api/events';

  return fetchApi<GeneratedEventListResponse>(endpoint);
}

export async function fetchEvent(id: number): Promise<Event> {
  return fetchApi<Event>(`/api/events/${id}`);
}

export interface EventUpdateData {
  reviewed?: boolean;
  notes?: string | null;
}

export async function updateEvent(id: number, data: EventUpdateData): Promise<Event> {
  return fetchApi<Event>(`/api/events/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export interface BulkUpdateResult {
  successful: number[];
  failed: Array<{ id: number; error: string }>;
}

export async function bulkUpdateEvents(
  eventIds: number[],
  data: EventUpdateData
): Promise<BulkUpdateResult> {
  const results: BulkUpdateResult = {
    successful: [],
    failed: [],
  };

  // Execute updates in parallel for better performance
  const updatePromises = eventIds.map(async (id) => {
    try {
      await updateEvent(id, data);
      results.successful.push(id);
    } catch (error) {
      results.failed.push({
        id,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  });

  await Promise.all(updatePromises);
  return results;
}

// ============================================================================
// Detection Endpoints
// ============================================================================

export async function fetchEventDetections(
  eventId: number,
  params?: { limit?: number; offset?: number }
): Promise<GeneratedDetectionListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/events/${eventId}/detections?${queryString}`
    : `/api/events/${eventId}/detections`;

  return fetchApi<GeneratedDetectionListResponse>(endpoint);
}

// ============================================================================
// Media URLs
// ============================================================================

export function getMediaUrl(cameraId: string, filename: string): string {
  return `${BASE_URL}/api/media/cameras/${cameraId}/${filename}`;
}

export function getThumbnailUrl(filename: string): string {
  return `${BASE_URL}/api/media/thumbnails/${filename}`;
}

// ============================================================================
// Logs Endpoints
// ============================================================================

export async function fetchLogStats(): Promise<LogStats> {
  return fetchApi<LogStats>('/api/logs/stats');
}

export interface LogsQueryParams {
  level?: string;
  component?: string;
  camera_id?: string;
  source?: string;
  search?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export async function fetchLogs(params?: LogsQueryParams): Promise<GeneratedLogsResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.level) queryParams.append('level', params.level);
    if (params.component) queryParams.append('component', params.component);
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
    if (params.source) queryParams.append('source', params.source);
    if (params.search) queryParams.append('search', params.search);
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/logs?${queryString}` : '/api/logs';

  return fetchApi<GeneratedLogsResponse>(endpoint);
}

export function getDetectionImageUrl(detectionId: number): string {
  return `${BASE_URL}/api/detections/${detectionId}/image`;
}
