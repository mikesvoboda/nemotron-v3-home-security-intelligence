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
  AuditLogListResponse,
  AuditLogResponse,
  AuditLogStats,
  Camera,
  CameraCreate,
  CameraListResponse,
  CameraUpdate,
  CleanupResponse,
  Detection,
  DetectionListResponse,
  DLQClearResponse,
  DLQJobResponse,
  DLQJobsResponse,
  DLQName,
  DLQRequeueResponse,
  DLQStatsResponse,
  Event,
  EventListResponse,
  EventStatsResponse,
  FrontendLogCreate,
  GPUStats,
  GPUStatsSample,
  GPUStatsHistoryResponse,
  HealthResponse,
  HTTPValidationError,
  LivenessResponse,
  LogEntry,
  LogsResponse,
  LogStats,
  MediaErrorResponse,
  PipelineLatencies,
  QueueDepths,
  ReadinessResponse,
  SearchResponse,
  SearchResult,
  ServiceStatus,
  StageLatency,
  SystemConfig,
  SystemConfigUpdate,
  SystemStats,
  TelemetryResponse,
  ValidationError,
  WorkerStatus,
} from '../types/generated';

// Import concrete types for use in this module
import type {
  AuditLogListResponse as GeneratedAuditLogListResponse,
  AuditLogResponse as GeneratedAuditLogResponse,
  AuditLogStats as GeneratedAuditLogStats,
  Camera,
  CameraCreate,
  CameraListResponse as GeneratedCameraListResponse,
  CameraUpdate,
  CleanupResponse,
  DetectionListResponse as GeneratedDetectionListResponse,
  DLQClearResponse as GeneratedDLQClearResponse,
  DLQJobsResponse as GeneratedDLQJobsResponse,
  DLQRequeueResponse as GeneratedDLQRequeueResponse,
  DLQStatsResponse as GeneratedDLQStatsResponse,
  Event,
  EventListResponse as GeneratedEventListResponse,
  EventStatsResponse as GeneratedEventStatsResponse,
  GPUStats,
  GPUStatsHistoryResponse,
  HealthResponse,
  LogsResponse as GeneratedLogsResponse,
  LogStats,
  ReadinessResponse,
  SearchResponse as GeneratedSearchResponse,
  SystemConfig,
  SystemConfigUpdate,
  SystemStats,
  TelemetryResponse,
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
// Audit Log Endpoints
// ============================================================================

/**
 * Query parameters for fetching audit logs
 */
export interface AuditLogsQueryParams {
  /** Filter by action type */
  action?: string;
  /** Filter by resource type */
  resource_type?: string;
  /** Filter by resource ID */
  resource_id?: string;
  /** Filter by actor */
  actor?: string;
  /** Filter by status (success/failure) */
  status?: string;
  /** Filter from date (ISO format) */
  start_date?: string;
  /** Filter to date (ISO format) */
  end_date?: string;
  /** Page size (default 100, max 1000) */
  limit?: number;
  /** Page offset */
  offset?: number;
}

/**
 * Fetch audit logs with optional filtering and pagination.
 *
 * @param params - Query parameters for filtering
 * @returns AuditLogListResponse with logs and pagination info
 */
export async function fetchAuditLogs(
  params?: AuditLogsQueryParams
): Promise<GeneratedAuditLogListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.action) queryParams.append('action', params.action);
    if (params.resource_type) queryParams.append('resource_type', params.resource_type);
    if (params.resource_id) queryParams.append('resource_id', params.resource_id);
    if (params.actor) queryParams.append('actor', params.actor);
    if (params.status) queryParams.append('status', params.status);
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/audit?${queryString}` : '/api/audit';

  return fetchApi<GeneratedAuditLogListResponse>(endpoint);
}

/**
 * Fetch audit log statistics for dashboard display.
 *
 * @returns AuditLogStats with aggregated statistics
 */
export async function fetchAuditStats(): Promise<GeneratedAuditLogStats> {
  return fetchApi<GeneratedAuditLogStats>('/api/audit/stats');
}

/**
 * Fetch a single audit log entry by ID.
 *
 * @param id - Audit log ID
 * @returns AuditLogResponse with log details
 */
export async function fetchAuditLog(id: number): Promise<GeneratedAuditLogResponse> {
  return fetchApi<GeneratedAuditLogResponse>(`/api/audit/${id}`);
}
