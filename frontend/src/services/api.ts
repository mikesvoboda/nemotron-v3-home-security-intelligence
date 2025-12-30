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
  ReadinessResponse,
  WorkerStatus,
  TelemetryResponse,
  QueueDepths,
  PipelineLatencies,
  StageLatency,
  PipelineLatencyResponse,
  PipelineStageLatency,
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
  SearchResult,
  SearchResponse,
  Zone,
  ZoneCreate,
  ZoneUpdate,
  ZoneListResponse,
  ZoneType,
  ZoneShape,
} from '../types/generated';

// Import concrete types for use in this module
import type {
  Camera,
  CameraCreate,
  CameraUpdate,
  CameraListResponse as GeneratedCameraListResponse,
  Event,
  EventListResponse as GeneratedEventListResponse,
  EventStatsResponse as GeneratedEventStatsResponse,
  DetectionListResponse as GeneratedDetectionListResponse,
  HealthResponse,
  GPUStats,
  GPUStatsHistoryResponse,
  SystemConfig,
  SystemConfigUpdate,
  SystemStats,
  LogsResponse as GeneratedLogsResponse,
  LogStats,
  CleanupResponse,
  TelemetryResponse,
  ReadinessResponse,
  PipelineLatencyResponse,
  DLQStatsResponse as GeneratedDLQStatsResponse,
  DLQJobsResponse as GeneratedDLQJobsResponse,
  DLQRequeueResponse as GeneratedDLQRequeueResponse,
  DLQClearResponse as GeneratedDLQClearResponse,
  SearchResponse as GeneratedSearchResponse,
  Zone,
  ZoneCreate,
  ZoneUpdate,
  ZoneListResponse as GeneratedZoneListResponse,
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

/**
 * Get the URL for a camera's latest snapshot.
 * This URL can be used directly in an img src attribute.
 * When API key authentication is enabled, the key is appended as a query parameter.
 *
 * @param cameraId - The camera UUID
 * @returns The full URL to the camera's snapshot endpoint
 */
export function getCameraSnapshotUrl(cameraId: string): string {
  const baseUrl = `${BASE_URL}/api/cameras/${encodeURIComponent(cameraId)}/snapshot`;
  if (API_KEY) {
    return `${baseUrl}?api_key=${encodeURIComponent(API_KEY)}`;
  }
  return baseUrl;
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

export async function fetchGpuHistory(limit: number = 100): Promise<GPUStatsHistoryResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('limit', String(limit));
  return fetchApi<GPUStatsHistoryResponse>(`/api/system/gpu/history?${queryParams.toString()}`);
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

export async function fetchTelemetry(): Promise<TelemetryResponse> {
  return fetchApi<TelemetryResponse>('/api/system/telemetry');
}

/**
 * Fetch pipeline latency metrics with percentiles.
 *
 * Returns latency statistics for each stage transition in the AI pipeline:
 * - watch_to_detect: Time from file watcher detecting image to RT-DETR processing start
 * - detect_to_batch: Time from detection completion to batch aggregation
 * - batch_to_analyze: Time from batch completion to Nemotron analysis start
 * - total_pipeline: Total end-to-end processing time
 *
 * Each stage includes avg, min, max, p50, p95, p99 percentiles.
 *
 * @param windowMinutes - Time window for statistics calculation (default 60 minutes)
 * @returns PipelineLatencyResponse with latency statistics for each stage
 */
export async function fetchPipelineLatency(
  windowMinutes: number = 60
): Promise<PipelineLatencyResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('window_minutes', String(windowMinutes));
  return fetchApi<PipelineLatencyResponse>(
    `/api/system/pipeline-latency?${queryParams.toString()}`
  );
}

/**
 * Fetch system readiness status including background worker health.
 * Returns detailed status of all infrastructure services and background workers.
 *
 * @returns ReadinessResponse with service and worker status
 */
export async function fetchReadiness(): Promise<ReadinessResponse> {
  return fetchApi<ReadinessResponse>('/api/system/health/ready');
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

export interface EventStatsQueryParams {
  start_date?: string;
  end_date?: string;
}

export async function fetchEventStats(
  params?: EventStatsQueryParams
): Promise<GeneratedEventStatsResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/events/stats?${queryString}` : '/api/events/stats';

  return fetchApi<GeneratedEventStatsResponse>(endpoint);
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

/**
 * Helper function to append API key to a URL if configured.
 * Used by URL functions that return URLs for direct use in img/video src attributes.
 */
function appendApiKeyIfConfigured(url: string): string {
  if (API_KEY) {
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}api_key=${encodeURIComponent(API_KEY)}`;
  }
  return url;
}

export function getMediaUrl(cameraId: string, filename: string): string {
  const baseUrl = `${BASE_URL}/api/media/cameras/${cameraId}/${filename}`;
  return appendApiKeyIfConfigured(baseUrl);
}

export function getThumbnailUrl(filename: string): string {
  const baseUrl = `${BASE_URL}/api/media/thumbnails/${filename}`;
  return appendApiKeyIfConfigured(baseUrl);
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
  const baseUrl = `${BASE_URL}/api/detections/${detectionId}/image`;
  return appendApiKeyIfConfigured(baseUrl);
}

/**
 * Get the URL for streaming a detection video.
 * This URL can be used directly in a video src attribute.
 * The backend supports HTTP Range requests for efficient video streaming.
 * When API key authentication is enabled, the key is appended as a query parameter.
 *
 * @param detectionId - The detection ID
 * @returns The full URL to the detection's video stream endpoint
 */
export function getDetectionVideoUrl(detectionId: number): string {
  const baseUrl = `${BASE_URL}/api/detections/${detectionId}/video`;
  return appendApiKeyIfConfigured(baseUrl);
}

/**
 * Get the URL for a detection video's thumbnail.
 * Returns a poster image for the video player.
 * When API key authentication is enabled, the key is appended as a query parameter.
 *
 * @param detectionId - The detection ID
 * @returns The full URL to the detection's video thumbnail endpoint
 */
export function getDetectionVideoThumbnailUrl(detectionId: number): string {
  const baseUrl = `${BASE_URL}/api/detections/${detectionId}/video/thumbnail`;
  return appendApiKeyIfConfigured(baseUrl);
}

// ============================================================================
// DLQ Endpoints
// ============================================================================

/**
 * DLQ queue names matching backend DLQName enum
 */
export type DLQQueueName = 'dlq:detection_queue' | 'dlq:analysis_queue';

/**
 * Fetch DLQ statistics showing failed job counts.
 *
 * @returns DLQ stats with counts per queue and total
 */
export async function fetchDlqStats(): Promise<GeneratedDLQStatsResponse> {
  return fetchApi<GeneratedDLQStatsResponse>('/api/dlq/stats');
}

/**
 * Fetch jobs from a specific DLQ.
 *
 * @param queueName - The DLQ to fetch jobs from
 * @param start - Start index for pagination (default 0)
 * @param limit - Maximum jobs to return (default 100)
 * @returns List of jobs in the queue
 */
export async function fetchDlqJobs(
  queueName: DLQQueueName,
  start: number = 0,
  limit: number = 100
): Promise<GeneratedDLQJobsResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('start', String(start));
  queryParams.append('limit', String(limit));
  return fetchApi<GeneratedDLQJobsResponse>(
    `/api/dlq/jobs/${encodeURIComponent(queueName)}?${queryParams.toString()}`
  );
}

/**
 * Requeue a single job from a DLQ back to its processing queue.
 * Requires API key authentication.
 *
 * @param queueName - The DLQ to requeue from
 * @returns Result of the requeue operation
 */
export async function requeueDlqJob(queueName: DLQQueueName): Promise<GeneratedDLQRequeueResponse> {
  return fetchApi<GeneratedDLQRequeueResponse>(
    `/api/dlq/requeue/${encodeURIComponent(queueName)}`,
    { method: 'POST' }
  );
}

/**
 * Requeue all jobs from a DLQ back to their processing queue.
 * Requires API key authentication.
 *
 * @param queueName - The DLQ to requeue from
 * @returns Result of the requeue operation with count
 */
export async function requeueAllDlqJobs(
  queueName: DLQQueueName
): Promise<GeneratedDLQRequeueResponse> {
  return fetchApi<GeneratedDLQRequeueResponse>(
    `/api/dlq/requeue-all/${encodeURIComponent(queueName)}`,
    { method: 'POST' }
  );
}

/**
 * Clear all jobs from a DLQ.
 * Requires API key authentication.
 * WARNING: This permanently removes all jobs.
 *
 * @param queueName - The DLQ to clear
 * @returns Result of the clear operation
 */
export async function clearDlq(queueName: DLQQueueName): Promise<GeneratedDLQClearResponse> {
  return fetchApi<GeneratedDLQClearResponse>(`/api/dlq/${encodeURIComponent(queueName)}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Export Endpoints
// ============================================================================

export interface ExportQueryParams {
  camera_id?: string;
  risk_level?: string;
  start_date?: string;
  end_date?: string;
  reviewed?: boolean;
}

/**
 * Export events as CSV file.
 * Triggers a file download with the exported data.
 *
 * @param params - Optional filter parameters for export
 * @returns Promise that resolves when download is triggered
 */
export async function exportEventsCSV(params?: ExportQueryParams): Promise<void> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
    if (params.risk_level) queryParams.append('risk_level', params.risk_level);
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.reviewed !== undefined) queryParams.append('reviewed', String(params.reviewed));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/events/export?${queryString}` : '/api/events/export';
  const url = `${BASE_URL}${endpoint}`;

  // Build headers with optional API key
  const headers: HeadersInit = {};
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }

  try {
    const response = await fetch(url, { headers });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorBody: unknown = await response.json();
        if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
          errorMessage = String((errorBody as { detail: unknown }).detail);
        }
      } catch {
        // If response body is not JSON, use status text
      }
      throw new ApiError(response.status, errorMessage);
    }

    // Get filename from Content-Disposition header or generate default
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `events_export_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.csv`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
      if (match?.[1]) {
        filename = match[1];
      }
    }

    // Get the blob and trigger download
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(0, error instanceof Error ? error.message : 'Export request failed');
  }
}

// ============================================================================
// Search Endpoints
// ============================================================================

/**
 * Parameters for searching events with full-text search
 */
export interface EventSearchParams {
  /** Search query string (required) */
  q: string;
  /** Filter by camera IDs (comma-separated for multiple) */
  camera_id?: string;
  /** Filter by start date (ISO format) */
  start_date?: string;
  /** Filter by end date (ISO format) */
  end_date?: string;
  /** Filter by risk levels (comma-separated: low,medium,high,critical) */
  severity?: string;
  /** Filter by object types (comma-separated: person,vehicle,animal) */
  object_type?: string;
  /** Filter by reviewed status */
  reviewed?: boolean;
  /** Maximum number of results (default 50) */
  limit?: number;
  /** Number of results to skip for pagination */
  offset?: number;
}

/**
 * Search events using PostgreSQL full-text search.
 *
 * Supports advanced query syntax:
 * - Basic words: "person vehicle" (implicit AND)
 * - Phrase search: '"suspicious person"' (exact phrase)
 * - Boolean OR: "person OR animal"
 * - Boolean NOT: "person NOT cat"
 * - Boolean AND: "person AND vehicle" (explicit)
 *
 * Results are ranked by relevance score.
 *
 * @param params - Search parameters including query and optional filters
 * @returns SearchResponse with relevance-ranked results and pagination info
 */
export async function searchEvents(params: EventSearchParams): Promise<GeneratedSearchResponse> {
  const queryParams = new URLSearchParams();

  // Query is required
  queryParams.append('q', params.q);

  // Optional filters
  if (params.camera_id) queryParams.append('camera_id', params.camera_id);
  if (params.start_date) queryParams.append('start_date', params.start_date);
  if (params.end_date) queryParams.append('end_date', params.end_date);
  if (params.severity) queryParams.append('severity', params.severity);
  if (params.object_type) queryParams.append('object_type', params.object_type);
  if (params.reviewed !== undefined) queryParams.append('reviewed', String(params.reviewed));
  if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
  if (params.offset !== undefined) queryParams.append('offset', String(params.offset));

  return fetchApi<GeneratedSearchResponse>(`/api/events/search?${queryParams.toString()}`);
}

// ============================================================================
// Storage Types (defined locally until types are regenerated)
// ============================================================================

/**
 * Storage statistics for a single category.
 */
export interface StorageCategoryStats {
  /** Number of files in this category */
  file_count: number;
  /** Total size in bytes for this category */
  size_bytes: number;
}

/**
 * Response schema for storage statistics endpoint.
 */
export interface StorageStatsResponse {
  /** Total disk space used in bytes */
  disk_used_bytes: number;
  /** Total disk space available in bytes */
  disk_total_bytes: number;
  /** Free disk space in bytes */
  disk_free_bytes: number;
  /** Disk usage percentage (0-100) */
  disk_usage_percent: number;
  /** Storage used by detection thumbnails */
  thumbnails: StorageCategoryStats;
  /** Storage used by original camera images */
  images: StorageCategoryStats;
  /** Storage used by event video clips */
  clips: StorageCategoryStats;
  /** Total number of events in database */
  events_count: number;
  /** Total number of detections in database */
  detections_count: number;
  /** Total number of GPU stats records in database */
  gpu_stats_count: number;
  /** Total number of log entries in database */
  logs_count: number;
  /** Timestamp of storage stats snapshot */
  timestamp: string;
}

// ============================================================================
// Storage Endpoints
// ============================================================================

/**
 * Fetch storage statistics and disk usage metrics.
 *
 * @returns StorageStatsResponse with disk usage and storage breakdown
 */
export async function fetchStorageStats(): Promise<StorageStatsResponse> {
  return fetchApi<StorageStatsResponse>('/api/system/storage');
}

/**
 * Trigger cleanup with dry run mode to preview what would be deleted.
 *
 * @returns CleanupResponse with counts of what would be deleted
 */
export async function previewCleanup(): Promise<CleanupResponse> {
  return fetchApi<CleanupResponse>('/api/system/cleanup?dry_run=true', {
    method: 'POST',
  });
}

// ============================================================================
// Severity Types & Endpoints
// ============================================================================

/**
 * Severity levels for risk classification.
 */
export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Current severity threshold configuration.
 */
export interface SeverityThresholds {
  /** Maximum risk score for LOW severity (0 to this value = LOW) */
  low_max: number;
  /** Maximum risk score for MEDIUM severity (low_max+1 to this value = MEDIUM) */
  medium_max: number;
  /** Maximum risk score for HIGH severity (medium_max+1 to this value = HIGH) */
  high_max: number;
}

/**
 * Definition of a single severity level.
 */
export interface SeverityDefinitionResponse {
  /** The severity level identifier */
  severity: SeverityLevel;
  /** Human-readable label for the severity level */
  label: string;
  /** Description of when this severity applies */
  description: string;
  /** Hex color code for UI display (e.g., '#22c55e') */
  color: string;
  /** Sort priority (0 = highest priority, 3 = lowest) */
  priority: number;
  /** Minimum risk score for this severity (inclusive) */
  min_score: number;
  /** Maximum risk score for this severity (inclusive) */
  max_score: number;
}

/**
 * Response schema for severity metadata endpoint.
 */
export interface SeverityMetadataResponse {
  /** List of all severity level definitions */
  definitions: SeverityDefinitionResponse[];
  /** Current severity threshold configuration */
  thresholds: SeverityThresholds;
}

/**
 * Fetch severity metadata including definitions and thresholds.
 *
 * Returns complete information about the severity taxonomy including:
 * - All severity level definitions (LOW, MEDIUM, HIGH, CRITICAL)
 * - Risk score thresholds for each level
 * - Color codes for UI display
 * - Human-readable labels and descriptions
 *
 * @returns SeverityMetadataResponse with all severity definitions and current thresholds
 */
export async function fetchSeverityMetadata(): Promise<SeverityMetadataResponse> {
  return fetchApi<SeverityMetadataResponse>('/api/system/severity');
}

// ============================================================================
// Notification Endpoints
// ============================================================================

/**
 * Notification channel types
 */
export type NotificationChannel = 'email' | 'webhook' | 'push';

/**
 * Notification configuration status
 */
export interface NotificationConfig {
  notification_enabled: boolean;
  email_configured: boolean;
  webhook_configured: boolean;
  push_configured: boolean;
  available_channels: NotificationChannel[];
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_from_address: string | null;
  smtp_use_tls: boolean | null;
  default_webhook_url: string | null;
  webhook_timeout_seconds: number | null;
  default_email_recipients: string[];
}

/**
 * Test notification result
 */
export interface TestNotificationResult {
  channel: NotificationChannel;
  success: boolean;
  error: string | null;
  message: string;
}

/**
 * Fetch notification configuration status.
 *
 * @returns NotificationConfig with current notification settings
 */
export async function fetchNotificationConfig(): Promise<NotificationConfig> {
  return fetchApi<NotificationConfig>('/api/notification/config');
}

/**
 * Test notification delivery for a specific channel.
 *
 * @param channel - The notification channel to test (email, webhook, push)
 * @param recipients - Optional email recipients (for email channel)
 * @param webhookUrl - Optional webhook URL (for webhook channel)
 * @returns TestNotificationResult with test outcome
 */
export async function testNotification(
  channel: NotificationChannel,
  recipients?: string[],
  webhookUrl?: string
): Promise<TestNotificationResult> {
  const body: { channel: NotificationChannel; email_recipients?: string[]; webhook_url?: string } =
    {
      channel,
    };

  if (recipients && recipients.length > 0) {
    body.email_recipients = recipients;
  }

  if (webhookUrl) {
    body.webhook_url = webhookUrl;
  }

  return fetchApi<TestNotificationResult>('/api/notification/test', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ============================================================================
// Circuit Breaker Types
// ============================================================================

/**
 * Circuit breaker states
 */
export type CircuitBreakerState = 'closed' | 'open' | 'half_open';

/**
 * Configuration for a circuit breaker.
 */
export interface CircuitBreakerConfig {
  /** Number of failures before opening circuit */
  failure_threshold: number;
  /** Seconds to wait before transitioning to half-open */
  recovery_timeout: number;
  /** Maximum calls allowed in half-open state */
  half_open_max_calls: number;
  /** Successes needed in half-open to close circuit */
  success_threshold: number;
}

/**
 * Status of a single circuit breaker.
 */
export interface CircuitBreakerStatus {
  /** Circuit breaker name */
  name: string;
  /** Current circuit state */
  state: CircuitBreakerState;
  /** Current consecutive failure count */
  failure_count: number;
  /** Current consecutive success count (relevant in half-open) */
  success_count: number;
  /** Total calls attempted through this circuit */
  total_calls: number;
  /** Calls rejected due to open circuit */
  rejected_calls: number;
  /** Monotonic time of last failure (seconds) */
  last_failure_time: number | null;
  /** Monotonic time when circuit opened (seconds) */
  opened_at: number | null;
  /** Circuit breaker configuration */
  config: CircuitBreakerConfig;
}

/**
 * Response for circuit breakers status endpoint.
 */
export interface CircuitBreakersResponse {
  /** Status of all circuit breakers keyed by name */
  circuit_breakers: Record<string, CircuitBreakerStatus>;
  /** Total number of circuit breakers */
  total_count: number;
  /** Number of circuit breakers currently open */
  open_count: number;
  /** Timestamp of status snapshot */
  timestamp: string;
}

/**
 * Response for circuit breaker reset operation.
 */
export interface CircuitBreakerResetResponse {
  /** Name of the circuit breaker that was reset */
  name: string;
  /** State before reset */
  previous_state: CircuitBreakerState;
  /** State after reset (should be closed) */
  new_state: CircuitBreakerState;
  /** Human-readable result message */
  message: string;
}

// ============================================================================
// Cleanup Status Types
// ============================================================================

/**
 * Response for cleanup service status endpoint.
 */
export interface CleanupStatusResponse {
  /** Whether the cleanup service is currently running */
  running: boolean;
  /** Current retention period in days */
  retention_days: number;
  /** Scheduled daily cleanup time in HH:MM format */
  cleanup_time: string;
  /** Whether original images are deleted during cleanup */
  delete_images: boolean;
  /** ISO timestamp of next scheduled cleanup (null if not running) */
  next_cleanup: string | null;
  /** Timestamp of status snapshot */
  timestamp: string;
}

// ============================================================================
// Circuit Breaker Endpoints
// ============================================================================

/**
 * Fetch status of all circuit breakers.
 *
 * @returns CircuitBreakersResponse with status of all circuit breakers
 */
export async function fetchCircuitBreakers(): Promise<CircuitBreakersResponse> {
  return fetchApi<CircuitBreakersResponse>('/api/system/circuit-breakers');
}

/**
 * Reset a specific circuit breaker to CLOSED state.
 * Requires API key authentication.
 *
 * @param name - Name of the circuit breaker to reset
 * @returns CircuitBreakerResetResponse with reset confirmation
 */
export async function resetCircuitBreaker(name: string): Promise<CircuitBreakerResetResponse> {
  return fetchApi<CircuitBreakerResetResponse>(
    `/api/system/circuit-breakers/${encodeURIComponent(name)}/reset`,
    { method: 'POST' }
  );
}

// ============================================================================
// Cleanup Status Endpoints
// ============================================================================

/**
 * Fetch current status of the cleanup service.
 *
 * @returns CleanupStatusResponse with cleanup service status
 */
export async function fetchCleanupStatus(): Promise<CleanupStatusResponse> {
  return fetchApi<CleanupStatusResponse>('/api/system/cleanup/status');
}

// ============================================================================
// Alert Rules Types
// ============================================================================

/**
 * Alert severity levels
 */
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';

/**
 * Alert rule schedule for time-based conditions
 */
export interface AlertRuleSchedule {
  /** Days of week when rule is active (empty = all days) */
  days?: string[] | null;
  /** Start time in HH:MM format */
  start_time?: string | null;
  /** End time in HH:MM format */
  end_time?: string | null;
  /** Timezone for time evaluation */
  timezone?: string;
}

/**
 * Alert rule response from API
 */
export interface AlertRule {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  severity: AlertSeverity;
  risk_threshold: number | null;
  object_types: string[] | null;
  camera_ids: string[] | null;
  zone_ids: string[] | null;
  min_confidence: number | null;
  schedule: AlertRuleSchedule | null;
  conditions: Record<string, unknown> | null;
  dedup_key_template: string;
  cooldown_seconds: number;
  channels: string[];
  created_at: string;
  updated_at: string;
}

/**
 * Create alert rule request
 */
export interface AlertRuleCreate {
  name: string;
  description?: string | null;
  enabled?: boolean;
  severity?: AlertSeverity;
  risk_threshold?: number | null;
  object_types?: string[] | null;
  camera_ids?: string[] | null;
  zone_ids?: string[] | null;
  min_confidence?: number | null;
  schedule?: AlertRuleSchedule | null;
  dedup_key_template?: string;
  cooldown_seconds?: number;
  channels?: string[];
}

/**
 * Update alert rule request (partial)
 */
export interface AlertRuleUpdate {
  name?: string;
  description?: string | null;
  enabled?: boolean;
  severity?: AlertSeverity;
  risk_threshold?: number | null;
  object_types?: string[] | null;
  camera_ids?: string[] | null;
  zone_ids?: string[] | null;
  min_confidence?: number | null;
  schedule?: AlertRuleSchedule | null;
  dedup_key_template?: string;
  cooldown_seconds?: number;
  channels?: string[];
}

/**
 * Alert rules list response
 */
export interface AlertRuleListResponse {
  rules: AlertRule[];
  count: number;
  limit: number;
  offset: number;
}

/**
 * Query parameters for listing alert rules
 */
export interface AlertRulesQueryParams {
  enabled?: boolean;
  severity?: AlertSeverity;
  limit?: number;
  offset?: number;
}

// ============================================================================
// Alert Rules Endpoints
// ============================================================================

/**
 * Fetch all alert rules with optional filtering.
 *
 * @param params - Optional query parameters for filtering
 * @returns AlertRuleListResponse with rules and pagination info
 */
export async function fetchAlertRules(
  params?: AlertRulesQueryParams
): Promise<AlertRuleListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.enabled !== undefined) queryParams.append('enabled', String(params.enabled));
    if (params.severity) queryParams.append('severity', params.severity);
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/alerts/rules?${queryString}` : '/api/alerts/rules';

  return fetchApi<AlertRuleListResponse>(endpoint);
}

/**
 * Fetch a single alert rule by ID.
 *
 * @param ruleId - The rule UUID
 * @returns AlertRule
 */
export async function fetchAlertRule(ruleId: string): Promise<AlertRule> {
  return fetchApi<AlertRule>(`/api/alerts/rules/${encodeURIComponent(ruleId)}`);
}

/**
 * Create a new alert rule.
 *
 * @param data - Rule creation data
 * @returns Created AlertRule
 */
export async function createAlertRule(data: AlertRuleCreate): Promise<AlertRule> {
  return fetchApi<AlertRule>('/api/alerts/rules', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing alert rule.
 *
 * @param ruleId - The rule UUID to update
 * @param data - Partial update data
 * @returns Updated AlertRule
 */
export async function updateAlertRule(ruleId: string, data: AlertRuleUpdate): Promise<AlertRule> {
  return fetchApi<AlertRule>(`/api/alerts/rules/${encodeURIComponent(ruleId)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete an alert rule.
 *
 * @param ruleId - The rule UUID to delete
 */
export async function deleteAlertRule(ruleId: string): Promise<void> {
  return fetchApi<void>(`/api/alerts/rules/${encodeURIComponent(ruleId)}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Zone Endpoints
// ============================================================================

/**
 * Fetch all zones for a camera.
 *
 * @param cameraId - The camera UUID
 * @param enabled - Optional filter by enabled status
 * @returns Array of zones for the camera
 */
export async function fetchZones(cameraId: string, enabled?: boolean): Promise<Zone[]> {
  const queryParams = new URLSearchParams();
  if (enabled !== undefined) {
    queryParams.append('enabled', String(enabled));
  }
  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/cameras/${encodeURIComponent(cameraId)}/zones?${queryString}`
    : `/api/cameras/${encodeURIComponent(cameraId)}/zones`;

  const response = await fetchApi<GeneratedZoneListResponse>(endpoint);
  return response.zones;
}

/**
 * Fetch a single zone by ID.
 *
 * @param cameraId - The camera UUID
 * @param zoneId - The zone UUID
 * @returns Zone object
 */
export async function fetchZone(cameraId: string, zoneId: string): Promise<Zone> {
  return fetchApi<Zone>(
    `/api/cameras/${encodeURIComponent(cameraId)}/zones/${encodeURIComponent(zoneId)}`
  );
}

/**
 * Create a new zone for a camera.
 *
 * @param cameraId - The camera UUID
 * @param data - Zone creation data
 * @returns Created zone object
 */
export async function createZone(cameraId: string, data: ZoneCreate): Promise<Zone> {
  return fetchApi<Zone>(`/api/cameras/${encodeURIComponent(cameraId)}/zones`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing zone.
 *
 * @param cameraId - The camera UUID
 * @param zoneId - The zone UUID to update
 * @param data - Zone update data (partial)
 * @returns Updated zone object
 */
export async function updateZone(
  cameraId: string,
  zoneId: string,
  data: ZoneUpdate
): Promise<Zone> {
  return fetchApi<Zone>(
    `/api/cameras/${encodeURIComponent(cameraId)}/zones/${encodeURIComponent(zoneId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(data),
    }
  );
}

/**
 * Delete a zone.
 *
 * @param cameraId - The camera UUID
 * @param zoneId - The zone UUID to delete
 */
export async function deleteZone(cameraId: string, zoneId: string): Promise<void> {
  return fetchApi<void>(
    `/api/cameras/${encodeURIComponent(cameraId)}/zones/${encodeURIComponent(zoneId)}`,
    {
      method: 'DELETE',
    }
  );
}

// ============================================================================
// Pipeline Status Types
// ============================================================================

/**
 * Degradation modes for system operation.
 */
export type DegradationMode = 'normal' | 'degraded' | 'minimal' | 'offline';

/**
 * Status information for the FileWatcher service.
 */
export interface FileWatcherStatus {
  /** Whether the file watcher is currently running */
  running: boolean;
  /** Root directory being watched for camera uploads */
  camera_root: string;
  /** Number of files pending processing (debouncing) */
  pending_tasks: number;
  /** Type of filesystem observer (native or polling) */
  observer_type: string;
}

/**
 * Information about an active batch.
 */
export interface BatchInfo {
  /** Unique batch identifier */
  batch_id: string;
  /** Camera ID this batch belongs to */
  camera_id: string;
  /** Number of detections in this batch */
  detection_count: number;
  /** Batch start time (Unix timestamp) */
  started_at: number;
  /** Time since batch started in seconds */
  age_seconds: number;
  /** Time since last activity in seconds */
  last_activity_seconds: number;
}

/**
 * Status information for the BatchAggregator service.
 */
export interface BatchAggregatorStatus {
  /** Number of active batches being aggregated */
  active_batches: number;
  /** Details of active batches */
  batches: BatchInfo[];
  /** Configured batch window timeout in seconds */
  batch_window_seconds: number;
  /** Configured idle timeout in seconds */
  idle_timeout_seconds: number;
}

/**
 * Health status of a registered service.
 */
export interface ServiceHealthStatus {
  /** Service name */
  name: string;
  /** Health status (healthy, unhealthy, unknown) */
  status: string;
  /** Monotonic time of last health check */
  last_check: number | null;
  /** Count of consecutive health check failures */
  consecutive_failures: number;
  /** Last error message if unhealthy */
  error_message: string | null;
}

/**
 * Status information for the DegradationManager service.
 */
export interface DegradationStatus {
  /** Current degradation mode */
  mode: DegradationMode;
  /** Whether system is in any degraded state */
  is_degraded: boolean;
  /** Whether Redis is healthy */
  redis_healthy: boolean;
  /** Number of jobs in in-memory fallback queue */
  memory_queue_size: number;
  /** Count of items in disk-based fallback queues by name */
  fallback_queues: Record<string, number>;
  /** Health status of registered services */
  services: ServiceHealthStatus[];
  /** Features available in current degradation mode */
  available_features: string[];
}

/**
 * Combined status of all pipeline operations.
 */
export interface PipelineStatusResponse {
  /** FileWatcher service status (null if not running) */
  file_watcher: FileWatcherStatus | null;
  /** BatchAggregator service status (null if not running) */
  batch_aggregator: BatchAggregatorStatus | null;
  /** DegradationManager service status (null if not initialized) */
  degradation: DegradationStatus | null;
  /** Timestamp of status snapshot */
  timestamp: string;
}

// ============================================================================
// Pipeline Status Endpoints
// ============================================================================

/**
 * Fetch pipeline operations status.
 *
 * Returns combined status of:
 * - FileWatcher: Monitoring camera directories for uploads
 * - BatchAggregator: Grouping detections into time-based batches
 * - DegradationManager: Graceful degradation and service health
 *
 * @returns PipelineStatusResponse with status of all pipeline services
 */
export async function fetchPipelineStatus(): Promise<PipelineStatusResponse> {
  return fetchApi<PipelineStatusResponse>('/api/system/pipeline');
}
