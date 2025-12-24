/**
 * API Client for Home Security Dashboard
 * Provides typed fetch wrappers for all REST endpoints
 */

// ============================================================================
// Types
// ============================================================================

export interface Camera {
  id: string;
  name: string;
  folder_path: string;
  status: string;
  created_at: string;
  last_seen_at: string | null;
}

export interface CameraCreate {
  name: string;
  folder_path: string;
  status?: string;
}

export interface CameraUpdate {
  name?: string;
  folder_path?: string;
  status?: string;
}

export interface HealthResponse {
  status: string;
  services: Record<string, string>;
  timestamp: string;
}

export interface GPUStats {
  utilization: number | null;
  memory_used: number | null;
  memory_total: number | null;
  temperature: number | null;
  inference_fps: number | null;
}

export interface SystemConfig {
  app_name: string;
  version: string;
  retention_days: number;
  batch_window_seconds: number;
  batch_idle_timeout_seconds: number;
}

export interface SystemStats {
  total_cameras: number;
  total_events: number;
  total_detections: number;
  uptime_seconds: number;
}

export interface Event {
  id: number;
  camera_id: string;
  started_at: string;
  ended_at: string | null;
  risk_score: number | null;
  risk_level: string | null;
  summary: string | null;
  reviewed: boolean;
  detection_count: number;
}

export interface EventListResponse {
  events: Event[];
  count: number;
  limit: number;
  offset: number;
}

export interface EventsQueryParams {
  camera_id?: string;
  risk_level?: string;
  start_date?: string;
  end_date?: string;
  reviewed?: boolean;
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

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
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

export interface CameraListResponse {
  cameras: Camera[];
  count: number;
}

export async function fetchCameras(): Promise<Camera[]> {
  const response = await fetchApi<CameraListResponse>('/api/cameras');
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

export async function fetchStats(): Promise<SystemStats> {
  return fetchApi<SystemStats>('/api/system/stats');
}

// ============================================================================
// Event Endpoints
// ============================================================================

export async function fetchEvents(params?: EventsQueryParams): Promise<EventListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
    if (params.risk_level) queryParams.append('risk_level', params.risk_level);
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.reviewed !== undefined) queryParams.append('reviewed', String(params.reviewed));
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/events?${queryString}` : '/api/events';

  return fetchApi<EventListResponse>(endpoint);
}

export async function fetchEvent(id: number): Promise<Event> {
  return fetchApi<Event>(`/api/events/${id}`);
}

export async function updateEvent(id: number, reviewed: boolean): Promise<Event> {
  return fetchApi<Event>(`/api/events/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ reviewed }),
  });
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

export interface LogStats {
  total_today: number;
  errors_today: number;
  warnings_today: number;
  by_component: Record<string, number>;
  by_level: Record<string, number>;
  top_component: string | null;
}

export async function fetchLogStats(): Promise<LogStats> {
  return fetchApi<LogStats>('/api/logs/stats');
}
