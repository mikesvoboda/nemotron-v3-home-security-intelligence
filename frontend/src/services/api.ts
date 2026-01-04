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
  AlertRule,
  AlertRuleCreate,
  AlertRuleListResponse,
  AlertRuleSchedule,
  AlertRuleUpdate,
  AlertSeverity,
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
  Zone,
  ZoneCreate,
  ZoneListResponse,
  ZoneShape,
  ZoneType,
  ZoneUpdate,
  // AI Audit types
  AiAuditStatsResponse,
  AiAuditLeaderboardResponse,
  AiAuditRecommendationsResponse,
  AiAuditEventAuditResponse,
  AiAuditModelContributions,
  AiAuditQualityScores,
  AiAuditPromptImprovements,
  AiAuditModelLeaderboardEntry,
  AiAuditRecommendationItem,
  // Circuit Breaker types
  CircuitBreakerStateEnum,
  CircuitBreakerConfigResponse,
  CircuitBreakerStatusResponse,
  CircuitBreakersResponse,
  CircuitBreakerResetResponse,
  // Severity types
  SeverityEnum,
  SeverityDefinitionResponse,
  SeverityThresholds,
  SeverityMetadataResponse,
} from '../types/generated';

// Import concrete types for use in this module
import type {
  AiAuditEventAuditResponse,
  AiAuditLeaderboardResponse,
  AiAuditRecommendationsResponse,
  AiAuditStatsResponse,
  AlertRule as GeneratedAlertRule,
  AlertRuleCreate as GeneratedAlertRuleCreate,
  AlertRuleListResponse as GeneratedAlertRuleListResponse,
  AlertRuleUpdate as GeneratedAlertRuleUpdate,
  AlertSeverity,
  AuditLogListResponse as GeneratedAuditLogListResponse,
  AuditLogResponse as GeneratedAuditLogResponse,
  AuditLogStats as GeneratedAuditLogStats,
  Camera,
  CameraCreate,
  CameraListResponse as GeneratedCameraListResponse,
  CameraUpdate,
  CircuitBreakerResetResponse as GeneratedCircuitBreakerResetResponse,
  CircuitBreakersResponse as GeneratedCircuitBreakersResponse,
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
  SeverityMetadataResponse as GeneratedSeverityMetadataResponse,
  SystemConfig,
  SystemConfigUpdate,
  SystemStats,
  TelemetryResponse,
  Zone,
  ZoneCreate,
  ZoneListResponse as GeneratedZoneListResponse,
  ZoneUpdate,
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

/**
 * Check if an error is an AbortError (request was cancelled via AbortController).
 * Used to gracefully handle cancelled requests when filters change rapidly.
 *
 * @param error - The error to check
 * @returns true if the error is an AbortError
 */
export function isAbortError(error: unknown): boolean {
  // Check both Error and DOMException (for cross-environment compatibility)
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true;
  }
  if (error instanceof Error && error.name === 'AbortError') {
    return true;
  }
  return false;
}

/**
 * Extended RequestInit that includes AbortSignal for request cancellation.
 * Used to cancel stale requests when filters change rapidly.
 */
export interface FetchOptions extends Omit<RequestInit, 'signal'> {
  /** AbortSignal for request cancellation */
  signal?: AbortSignal;
}

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL as string | undefined;

// ============================================================================
// Retry Configuration
// ============================================================================

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

/**
 * Determines if a request should be retried based on the HTTP status code.
 * Retries on network errors (status 0) and server errors (5xx).
 * Does not retry on client errors (4xx).
 */
export function shouldRetry(status: number): boolean {
  return status === 0 || (status >= 500 && status < 600);
}

/**
 * Calculates the delay for a retry attempt using exponential backoff.
 * @param attempt - The retry attempt number (0-indexed)
 * @returns Delay in milliseconds
 */
export function getRetryDelay(attempt: number): number {
  return BASE_DELAY_MS * Math.pow(2, attempt);
}

/**
 * Returns a promise that resolves after the specified delay.
 * @param ms - Delay in milliseconds
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================================
// Request Deduplication
// ============================================================================

const inFlightRequests = new Map<string, Promise<unknown>>();

/**
 * Generates a unique key for request deduplication.
 * Only GET requests are deduplicated; mutation requests always execute.
 * @param method - HTTP method
 * @param url - Full request URL
 * @returns Key string for GET requests, null for other methods
 */
export function getRequestKey(method: string, url: string): string | null {
  if (method.toUpperCase() !== 'GET') {
    return null;
  }
  return `${method.toUpperCase()}:${url}`;
}

/**
 * Returns the number of in-flight requests being tracked for deduplication.
 * Useful for testing and debugging.
 */
export function getInFlightRequestCount(): number {
  return inFlightRequests.size;
}

/**
 * Clears all tracked in-flight requests.
 * Primarily used for testing to reset state between tests.
 */
export function clearInFlightRequests(): void {
  inFlightRequests.clear();
}

// ============================================================================
// WebSocket URL and Protocol Helper
// ============================================================================

/**
 * WebSocket connection options including URL and optional protocol for authentication.
 */
export interface WebSocketConnectionOptions {
  /** The WebSocket URL to connect to */
  url: string;
  /** Optional Sec-WebSocket-Protocol header value for API key authentication */
  protocols?: string[];
}

/**
 * Internal function for building WebSocket connection options. Exported for testing.
 *
 * SECURITY: API keys are passed via the Sec-WebSocket-Protocol header instead of
 * query parameters to prevent exposure in browser history, server logs, and referrer headers.
 * The backend supports both "api-key.{key}" protocol format and query parameters for
 * backward compatibility, but the protocol header is preferred.
 *
 * @internal
 */
export function buildWebSocketOptionsInternal(
  endpoint: string,
  wsBaseUrl: string | undefined,
  apiKey: string | undefined,
  windowLocation: { protocol: string; host: string } | undefined
): WebSocketConnectionOptions {
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

  // Build connection options with optional API key protocol
  const options: WebSocketConnectionOptions = { url: wsUrl };

  if (apiKey) {
    // Use Sec-WebSocket-Protocol header for API key authentication
    // Format: "api-key.{key}" - the backend extracts the key after the prefix
    options.protocols = [`api-key.${apiKey}`];
  }

  return options;
}

/**
 * Constructs WebSocket connection options for the given endpoint.
 * Uses VITE_WS_BASE_URL if set, otherwise falls back to window.location.host.
 *
 * SECURITY: If VITE_API_KEY is set, returns a protocols array with "api-key.{key}"
 * for the Sec-WebSocket-Protocol header. This is more secure than query parameters
 * because it doesn't expose the API key in URLs.
 *
 * @param endpoint - The WebSocket endpoint path (e.g., '/ws/events')
 * @returns WebSocket connection options with URL and optional protocols
 */
export function buildWebSocketOptions(endpoint: string): WebSocketConnectionOptions {
  const windowLocation =
    typeof window !== 'undefined'
      ? { protocol: window.location.protocol, host: window.location.host }
      : undefined;
  return buildWebSocketOptionsInternal(endpoint, WS_BASE_URL, API_KEY, windowLocation);
}

/**
 * @deprecated Use buildWebSocketOptions instead. This function exposes API keys in URLs.
 * Kept for backward compatibility but will be removed in a future version.
 *
 * Internal function for building WebSocket URLs. Exported for testing.
 * @internal
 */
export function buildWebSocketUrlInternal(
  endpoint: string,
  wsBaseUrl: string | undefined,
  apiKey: string | undefined,
  windowLocation: { protocol: string; host: string } | undefined
): string {
  const options = buildWebSocketOptionsInternal(endpoint, wsBaseUrl, apiKey, windowLocation);
  // For backward compatibility, still append api_key to URL if configured
  // This maintains existing behavior but is deprecated
  if (apiKey) {
    const separator = options.url.includes('?') ? '&' : '?';
    return `${options.url}${separator}api_key=${encodeURIComponent(apiKey)}`;
  }
  return options.url;
}

/**
 * @deprecated Use buildWebSocketOptions instead. This function exposes API keys in URLs.
 * Kept for backward compatibility but will be removed in a future version.
 *
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

/**
 * Performs a fetch request with automatic retry on failure.
 * Uses exponential backoff for retry delays.
 * @param url - Full URL to fetch
 * @param options - Fetch options
 * @param retriesLeft - Number of retries remaining
 */
async function fetchWithRetry<T>(
  url: string,
  options: RequestInit,
  retriesLeft: number = MAX_RETRIES
): Promise<T> {
  try {
    const response = await fetch(url, options);

    // Check if we should retry based on status code
    if (!response.ok && shouldRetry(response.status) && retriesLeft > 0) {
      const delay = getRetryDelay(MAX_RETRIES - retriesLeft);
      await sleep(delay);
      return fetchWithRetry<T>(url, options, retriesLeft - 1);
    }

    return handleResponse<T>(response);
  } catch (error) {
    // Re-throw AbortError without wrapping - request was intentionally cancelled
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw error;
    }

    // For ApiErrors that are retryable, retry
    if (error instanceof ApiError) {
      if (shouldRetry(error.status) && retriesLeft > 0) {
        const delay = getRetryDelay(MAX_RETRIES - retriesLeft);
        await sleep(delay);
        return fetchWithRetry<T>(url, options, retriesLeft - 1);
      }
      throw error;
    }

    // Network errors - retry if we have retries left
    if (retriesLeft > 0) {
      const delay = getRetryDelay(MAX_RETRIES - retriesLeft);
      await sleep(delay);
      return fetchWithRetry<T>(url, options, retriesLeft - 1);
    }

    throw new ApiError(0, error instanceof Error ? error.message : 'Network request failed');
  }
}

async function fetchApi<T>(endpoint: string, options?: FetchOptions): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const method = options?.method || 'GET';

  // Build headers with optional API key
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options?.headers,
  };

  // Add API key header if configured
  if (API_KEY) {
    (headers as Record<string, string>)['X-API-Key'] = API_KEY;
  }

  const fetchOptions: RequestInit = {
    ...options,
    headers,
  };

  // Check if request has an abort signal - skip deduplication for these
  // to avoid race conditions with React Strict Mode's double-mounting
  const hasAbortSignal = options?.signal instanceof AbortSignal;

  // Check for request deduplication (only for GET requests WITHOUT abort signals)
  const requestKey = hasAbortSignal ? null : getRequestKey(method, url);

  if (requestKey) {
    // Check if there's already an in-flight request for this key
    const existingPromise = inFlightRequests.get(requestKey);
    if (existingPromise) {
      // Return the existing promise for duplicate requests
      return existingPromise as Promise<T>;
    }

    // Create a new request promise with cleanup
    const requestPromise = fetchWithRetry<T>(url, fetchOptions).finally(() => {
      // Clean up the in-flight request tracking when complete
      inFlightRequests.delete(requestKey);
    });

    // Track the in-flight request
    inFlightRequests.set(requestKey, requestPromise);

    return requestPromise;
  }

  // For non-GET requests, just execute with retry (no deduplication)
  return fetchWithRetry<T>(url, fetchOptions);
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
 *
 * Note: Camera snapshot endpoints are exempt from API key authentication
 * in the backend middleware, so no API key is needed in the URL.
 *
 * @param cameraId - The camera UUID
 * @returns The full URL to the camera's snapshot endpoint
 */
export function getCameraSnapshotUrl(cameraId: string): string {
  return `${BASE_URL}/api/cameras/${encodeURIComponent(cameraId)}/snapshot`;
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

export async function fetchEvents(
  params?: EventsQueryParams,
  options?: FetchOptions
): Promise<GeneratedEventListResponse> {
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

  return fetchApi<GeneratedEventListResponse>(endpoint, options);
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

/**
 * Detection statistics response from /api/detections/stats
 */
export interface DetectionStatsResponse {
  /** Total number of detections */
  total_detections: number;
  /** Detection counts grouped by object class (e.g., person, car, truck) */
  detections_by_class: Record<string, number>;
  /** Average confidence score across all detections */
  average_confidence: number | null;
}

/**
 * Fetch detection statistics including class distribution.
 *
 * Returns aggregate statistics about detections including counts by object class.
 * Used by the AI Performance page to display detection class distribution charts.
 *
 * @returns DetectionStatsResponse with detection statistics
 */
export async function fetchDetectionStats(): Promise<DetectionStatsResponse> {
  return fetchApi<DetectionStatsResponse>('/api/detections/stats');
}

// ============================================================================
// Media URLs
// ============================================================================

/**
 * Note: All media endpoints are exempt from API key authentication in the
 * backend middleware. Exempt endpoints include:
 * - /api/media/{path}
 * - /api/detections/{id}/image
 * - /api/detections/{id}/video
 * - /api/cameras/{id}/snapshot
 *
 * This is because:
 * 1. They are accessed directly by browsers via img/video tags
 * 2. They have their own security (path traversal protection, file type allowlist, rate limiting)
 * 3. Putting API keys in URLs exposes them in browser history, server logs, and referrer headers
 */

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

/**
 * Get the URL for streaming a detection video.
 * This URL can be used directly in a video src attribute.
 * The backend supports HTTP Range requests for efficient video streaming.
 *
 * Note: Detection media endpoints are exempt from API key authentication.
 *
 * @param detectionId - The detection ID
 * @returns The full URL to the detection's video stream endpoint
 */
export function getDetectionVideoUrl(detectionId: number): string {
  return `${BASE_URL}/api/detections/${detectionId}/video`;
}

/**
 * Get the URL for a detection video's thumbnail.
 * Returns a poster image for the video player.
 *
 * Note: Detection media endpoints are exempt from API key authentication.
 *
 * @param detectionId - The detection ID
 * @returns The full URL to the detection's video thumbnail endpoint
 */
export function getDetectionVideoThumbnailUrl(detectionId: number): string {
  return `${BASE_URL}/api/detections/${detectionId}/video/thumbnail`;
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
export async function searchEvents(
  params: EventSearchParams,
  options?: FetchOptions
): Promise<GeneratedSearchResponse> {
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

  return fetchApi<GeneratedSearchResponse>(`/api/events/search?${queryParams.toString()}`, options);
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
  params?: AuditLogsQueryParams,
  options?: FetchOptions
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

  return fetchApi<GeneratedAuditLogListResponse>(endpoint, options);
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

// ============================================================================
// Alert Rules Endpoints
// ============================================================================

/**
 * Query parameters for fetching alert rules
 */
export interface AlertRulesQueryParams {
  /** Filter by enabled status */
  enabled?: boolean;
  /** Filter by severity level */
  severity?: AlertSeverity;
  /** Maximum number of results (default 50) */
  limit?: number;
  /** Number of results to skip for pagination */
  offset?: number;
}

/**
 * Fetch all alert rules with optional filtering and pagination.
 *
 * @param params - Query parameters for filtering
 * @returns AlertRuleListResponse with rules and pagination info
 */
export async function fetchAlertRules(
  params?: AlertRulesQueryParams
): Promise<GeneratedAlertRuleListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.enabled !== undefined) queryParams.append('enabled', String(params.enabled));
    if (params.severity) queryParams.append('severity', params.severity);
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/alerts/rules?${queryString}` : '/api/alerts/rules';

  return fetchApi<GeneratedAlertRuleListResponse>(endpoint);
}

/**
 * Fetch a single alert rule by ID.
 *
 * @param id - Alert rule UUID
 * @returns AlertRule with rule details
 */
export async function fetchAlertRule(id: string): Promise<GeneratedAlertRule> {
  return fetchApi<GeneratedAlertRule>(`/api/alerts/rules/${id}`);
}

/**
 * Create a new alert rule.
 *
 * @param data - Alert rule creation data
 * @returns Created AlertRule
 */
export async function createAlertRule(data: GeneratedAlertRuleCreate): Promise<GeneratedAlertRule> {
  return fetchApi<GeneratedAlertRule>('/api/alerts/rules', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing alert rule.
 *
 * @param id - Alert rule UUID
 * @param data - Alert rule update data
 * @returns Updated AlertRule
 */
export async function updateAlertRule(
  id: string,
  data: GeneratedAlertRuleUpdate
): Promise<GeneratedAlertRule> {
  return fetchApi<GeneratedAlertRule>(`/api/alerts/rules/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete an alert rule.
 *
 * @param id - Alert rule UUID
 */
export async function deleteAlertRule(id: string): Promise<void> {
  return fetchApi<void>(`/api/alerts/rules/${id}`, {
    method: 'DELETE',
  });
}

/**
 * Test result for a single event
 */
export interface RuleTestEventResult {
  event_id: number;
  camera_id: string;
  risk_score: number | null;
  object_types: string[];
  matches: boolean;
  matched_conditions: string[];
  started_at: string | null;
}

/**
 * Response from testing an alert rule
 */
export interface RuleTestResponse {
  rule_id: string;
  rule_name: string;
  events_tested: number;
  events_matched: number;
  match_rate: number;
  results: RuleTestEventResult[];
}

/**
 * Request for testing an alert rule
 */
export interface RuleTestRequest {
  /** Specific event IDs to test against */
  event_ids?: number[];
  /** Maximum number of recent events to test (if event_ids not provided) */
  limit?: number;
  /** Override current time for schedule testing (ISO format) */
  test_time?: string;
}

/**
 * Test an alert rule against historical events.
 *
 * @param id - Alert rule UUID
 * @param request - Test request parameters
 * @returns RuleTestResponse with per-event match results
 */
export async function testAlertRule(id: string, request?: RuleTestRequest): Promise<RuleTestResponse> {
  return fetchApi<RuleTestResponse>(`/api/alerts/rules/${id}/test`, {
    method: 'POST',
    body: JSON.stringify(request || { limit: 10 }),
  });
}

// ============================================================================
// Zone Endpoints
// ============================================================================

/**
 * Fetch all zones for a camera.
 *
 * @param cameraId - Camera UUID
 * @param enabled - Optional filter by enabled status
 * @returns Zone list with all zones for the camera
 */
export async function fetchZones(
  cameraId: string,
  enabled?: boolean
): Promise<GeneratedZoneListResponse> {
  const queryParams = new URLSearchParams();
  if (enabled !== undefined) {
    queryParams.append('enabled', String(enabled));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/cameras/${cameraId}/zones?${queryString}`
    : `/api/cameras/${cameraId}/zones`;

  return fetchApi<GeneratedZoneListResponse>(endpoint);
}

/**
 * Fetch a single zone by ID.
 *
 * @param cameraId - Camera UUID
 * @param zoneId - Zone UUID
 * @returns Zone object
 */
export async function fetchZone(cameraId: string, zoneId: string): Promise<Zone> {
  return fetchApi<Zone>(`/api/cameras/${cameraId}/zones/${zoneId}`);
}

/**
 * Create a new zone for a camera.
 *
 * @param cameraId - Camera UUID
 * @param data - Zone creation data
 * @returns Created zone object
 */
export async function createZone(cameraId: string, data: ZoneCreate): Promise<Zone> {
  return fetchApi<Zone>(`/api/cameras/${cameraId}/zones`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing zone.
 *
 * @param cameraId - Camera UUID
 * @param zoneId - Zone UUID
 * @param data - Zone update data
 * @returns Updated zone object
 */
export async function updateZone(
  cameraId: string,
  zoneId: string,
  data: ZoneUpdate
): Promise<Zone> {
  return fetchApi<Zone>(`/api/cameras/${cameraId}/zones/${zoneId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a zone.
 *
 * @param cameraId - Camera UUID
 * @param zoneId - Zone UUID
 */
export async function deleteZone(cameraId: string, zoneId: string): Promise<void> {
  return fetchApi<void>(`/api/cameras/${cameraId}/zones/${zoneId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// AI Audit Endpoints
// ============================================================================

/**
 * Query parameters for AI audit statistics
 */
export interface AiAuditStatsQueryParams {
  /** Number of days to include in statistics (1-90, default 7) */
  days?: number;
  /** Filter by camera ID */
  camera_id?: string;
}

/**
 * Fetch aggregate AI audit statistics.
 *
 * Returns aggregate statistics including total events, quality scores,
 * model contribution rates, and audit trends over the specified period.
 *
 * @param params - Query parameters for filtering
 * @returns AiAuditStatsResponse with aggregate statistics
 */
export async function fetchAiAuditStats(
  params?: AiAuditStatsQueryParams
): Promise<AiAuditStatsResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.days !== undefined) queryParams.append('days', String(params.days));
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/ai-audit/stats?${queryString}` : '/api/ai-audit/stats';

  return fetchApi<AiAuditStatsResponse>(endpoint);
}

/**
 * Query parameters for model leaderboard
 */
export interface AiAuditLeaderboardQueryParams {
  /** Number of days to include (1-90, default 7) */
  days?: number;
}

/**
 * Fetch model leaderboard ranked by contribution rate.
 *
 * Returns a ranked list of AI models by their contribution rate,
 * along with quality correlation data.
 *
 * @param params - Query parameters for filtering
 * @returns AiAuditLeaderboardResponse with ranked model entries
 */
export async function fetchModelLeaderboard(
  params?: AiAuditLeaderboardQueryParams
): Promise<AiAuditLeaderboardResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.days !== undefined) queryParams.append('days', String(params.days));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/ai-audit/leaderboard?${queryString}`
    : '/api/ai-audit/leaderboard';

  return fetchApi<AiAuditLeaderboardResponse>(endpoint);
}

/**
 * Query parameters for recommendations
 */
export interface AiAuditRecommendationsQueryParams {
  /** Number of days to analyze (1-90, default 7) */
  days?: number;
}

/**
 * Fetch aggregated prompt improvement recommendations.
 *
 * Analyzes all audits to produce actionable recommendations for
 * improving the AI pipeline prompt templates.
 *
 * @param params - Query parameters for filtering
 * @returns AiAuditRecommendationsResponse with prioritized recommendations
 */
export async function fetchAuditRecommendations(
  params?: AiAuditRecommendationsQueryParams
): Promise<AiAuditRecommendationsResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.days !== undefined) queryParams.append('days', String(params.days));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/ai-audit/recommendations?${queryString}`
    : '/api/ai-audit/recommendations';

  return fetchApi<AiAuditRecommendationsResponse>(endpoint);
}

/**
 * Fetch audit information for a specific event.
 *
 * Retrieves the AI pipeline audit record for the given event, including
 * model contributions, quality scores, and prompt improvement suggestions.
 *
 * @param eventId - The ID of the event to get audit for
 * @returns AiAuditEventAuditResponse containing full audit details
 */
export async function fetchEventAudit(eventId: number): Promise<AiAuditEventAuditResponse> {
  return fetchApi<AiAuditEventAuditResponse>(`/api/ai-audit/events/${eventId}`);
}

// ============================================================================
// Circuit Breaker Endpoints
// ============================================================================

/**
 * Fetch all circuit breakers and their current status.
 *
 * Returns the state (closed/open/half_open), failure count, last failure time,
 * and configuration for each circuit breaker in the system.
 *
 * @returns CircuitBreakersResponse with status of all circuit breakers
 */
export async function fetchCircuitBreakers(): Promise<GeneratedCircuitBreakersResponse> {
  return fetchApi<GeneratedCircuitBreakersResponse>('/api/system/circuit-breakers');
}

/**
 * Reset a circuit breaker to the closed state.
 *
 * Manually resets a circuit breaker that is in the open or half_open state
 * back to the closed state, clearing its failure count.
 *
 * @param name - The name of the circuit breaker to reset
 * @returns CircuitBreakerResetResponse with reset confirmation
 * @throws ApiError 400 if name is invalid
 * @throws ApiError 404 if circuit breaker not found
 */
export async function resetCircuitBreaker(name: string): Promise<GeneratedCircuitBreakerResetResponse> {
  return fetchApi<GeneratedCircuitBreakerResetResponse>(
    `/api/system/circuit-breakers/${encodeURIComponent(name)}/reset`,
    { method: 'POST' }
  );
}

// ============================================================================
// Severity Metadata Endpoints
// ============================================================================

/**
 * Fetch severity metadata including definitions and thresholds.
 *
 * Returns complete information about all severity levels including:
 * - Severity definitions with labels, colors, and descriptions
 * - Risk score ranges for each severity level
 * - Current threshold configuration
 *
 * @returns SeverityMetadataResponse with all severity definitions and thresholds
 */
export async function fetchSeverityMetadata(): Promise<GeneratedSeverityMetadataResponse> {
  return fetchApi<GeneratedSeverityMetadataResponse>('/api/system/severity');
}

// Alias for backward compatibility - use existing SeverityMetadataResponse type
export const fetchSeverityConfig = fetchSeverityMetadata;

/**
 * Update severity threshold configuration.
 *
 * Allows customization of the risk score boundaries for each severity level.
 * The thresholds must satisfy: low_max < medium_max < high_max
 * to ensure contiguous, non-overlapping severity ranges.
 *
 * @param thresholds - New threshold values
 * @returns Updated SeverityMetadataResponse with new definitions
 * @throws ApiError 400 if thresholds are invalid or overlap
 */
export async function updateSeverityThresholds(thresholds: {
  low_max: number;
  medium_max: number;
  high_max: number;
}): Promise<GeneratedSeverityMetadataResponse> {
  return fetchApi<GeneratedSeverityMetadataResponse>('/api/system/severity', {
    method: 'PUT',
    body: JSON.stringify(thresholds),
  });
}

// ============================================================================
// Enrichment Endpoints
// ============================================================================

/**
 * License plate detection result
 */
export interface LicensePlateResult {
  detected: boolean;
  confidence?: number;
  text?: string;
  ocr_confidence?: number;
  bbox?: number[];
}

/**
 * Face detection result
 */
export interface FaceResult {
  detected: boolean;
  count: number;
  confidence?: number;
}

/**
 * Vehicle detection result
 */
export interface VehicleResult {
  type?: string;
  color?: string;
  confidence?: number;
  is_commercial?: boolean;
  damage_detected?: boolean;
  damage_types?: string[];
}

/**
 * Clothing detection result
 */
export interface ClothingResult {
  upper?: string;
  lower?: string;
  is_suspicious?: boolean;
  is_service_uniform?: boolean;
  has_face_covered?: boolean;
  has_bag?: boolean;
  clothing_items?: string[];
}

/**
 * Violence detection result
 */
export interface ViolenceResult {
  detected: boolean;
  score: number;
  confidence?: number;
}

/**
 * Image quality assessment result
 */
export interface ImageQualityResult {
  score: number;
  is_blurry: boolean;
  is_low_quality: boolean;
  quality_issues: string[];
  quality_change_detected?: boolean;
}

/**
 * Response from the enrichment API - contains results from 18+ vision models
 */
export interface EnrichmentResponse {
  detection_id: number;
  enriched_at: string | null;
  license_plate?: LicensePlateResult | null;
  face?: FaceResult | null;
  vehicle?: VehicleResult | null;
  clothing?: ClothingResult | null;
  violence?: ViolenceResult | null;
  weather?: unknown;
  pose?: unknown;
  depth?: unknown;
  image_quality?: ImageQualityResult | null;
  pet?: unknown;
  processing_time_ms?: number | null;
  errors?: string[];
}

/**
 * Fetch enrichment data for a specific detection.
 *
 * @param detectionId - The ID of the detection to get enrichment for
 * @returns EnrichmentResponse with AI-generated context about the detection
 */
export async function fetchDetectionEnrichment(detectionId: number): Promise<EnrichmentResponse> {
  return fetchApi<EnrichmentResponse>(`/api/enrichment/${detectionId}`);
}

// ============================================================================
// Model Zoo Endpoints
// ============================================================================

/**
 * Status information for a single AI model in the Model Zoo
 */
export interface ModelStatusResponse {
  name: string;
  display_name: string;
  vram_mb: number;
  status: 'loaded' | 'unloaded' | 'loading' | 'error' | 'disabled';
  category: string;
  enabled: boolean;
  available: boolean;
  path?: string;
  load_count?: number;
}

/**
 * Response from the model zoo status API
 */
export interface ModelRegistryResponse {
  models: ModelStatusResponse[];
  vram_budget_mb: number;
  vram_used_mb: number;
  vram_available_mb: number;
  loading_strategy?: string;
  max_concurrent_models?: number;
}

/**
 * Fetch model zoo status including all loaded models and memory usage.
 *
 * @returns ModelRegistryResponse with information about all registered AI models
 */
export async function fetchModelZooStatus(): Promise<ModelRegistryResponse> {
  return fetchApi<ModelRegistryResponse>('/api/system/models');
}

// ============================================================================
// Model Zoo Status and Latency Endpoints
// ============================================================================

/**
 * Status information for a Model Zoo model (compact format for status cards)
 */
export interface ModelZooStatusItem {
  name: string;
  display_name: string;
  category: string;
  status: 'loaded' | 'unloaded' | 'loading' | 'error' | 'disabled';
  vram_mb: number;
  last_used_at: string | null;
  enabled: boolean;
}

/**
 * Response from model zoo status endpoint
 */
export interface ModelZooStatusResponse {
  models: ModelZooStatusItem[];
  total_models: number;
  loaded_count: number;
  disabled_count: number;
  vram_budget_mb: number;
  vram_used_mb: number;
  timestamp: string;
}

/**
 * Latency statistics for a time bucket
 */
export interface ModelLatencyStats {
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  sample_count: number;
}

/**
 * Single time-bucket snapshot of model latency
 */
export interface ModelLatencySnapshot {
  timestamp: string;
  stats: ModelLatencyStats | null;
}

/**
 * Response from model latency history endpoint
 */
export interface ModelLatencyHistoryResponse {
  model_name: string;
  display_name: string;
  snapshots: ModelLatencySnapshot[];
  window_minutes: number;
  bucket_seconds: number;
  has_data: boolean;
  timestamp: string;
}

/**
 * Fetch compact status for all Model Zoo models.
 *
 * @returns ModelZooStatusResponse with status for all models
 */
export async function fetchModelZooCompactStatus(): Promise<ModelZooStatusResponse> {
  return fetchApi<ModelZooStatusResponse>('/api/system/model-zoo/status');
}

/**
 * Fetch latency history for a specific Model Zoo model.
 *
 * @param model - Model name (e.g., 'yolo11-license-plate')
 * @param since - Minutes of history to return (default 60)
 * @param bucketSeconds - Bucket size in seconds (default 60)
 * @returns ModelLatencyHistoryResponse with time-series data
 */
export async function fetchModelZooLatencyHistory(
  model: string,
  since: number = 60,
  bucketSeconds: number = 60
): Promise<ModelLatencyHistoryResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('model', model);
  queryParams.append('since', String(since));
  queryParams.append('bucket_seconds', String(bucketSeconds));
  return fetchApi<ModelLatencyHistoryResponse>(
    `/api/system/model-zoo/latency/history?${queryParams.toString()}`
  );
}

// ============================================================================
// Prompt Playground Endpoints
// ============================================================================

/**
 * Supported AI model names for prompt management
 */
export type PromptModelName = 'nemotron' | 'florence2' | 'yolo_world' | 'xclip' | 'fashion_clip';

/**
 * Response for a single model's prompt configuration
 */
export interface ModelPromptResponse {
  model_name: string;
  config: Record<string, unknown>;
  version: number;
  updated_at: string;
}

/**
 * Response containing prompts for all models
 */
export interface AllPromptsResponse {
  prompts: Record<string, ModelPromptResponse>;
}

/**
 * Response after updating a model's prompt
 */
export interface PromptUpdateResponse {
  model_name: string;
  version: number;
  message: string;
  config: Record<string, unknown>;
}

/**
 * Result from the original (current) prompt
 */
export interface PromptTestResultBefore {
  score: number;
  risk_level: string;
  summary: string;
}

/**
 * Result from the modified prompt
 */
export interface PromptTestResultAfter {
  score: number;
  risk_level: string;
  summary: string;
}

/**
 * Response from testing a modified prompt
 */
export interface PromptTestResponse {
  before: PromptTestResultBefore;
  after: PromptTestResultAfter;
  improved: boolean;
  inference_time_ms: number;
}

/**
 * A single entry in prompt version history
 */
export interface PromptHistoryEntry {
  version: number;
  config: Record<string, unknown>;
  created_at: string;
  created_by: string;
  description: string | null;
}

/**
 * Response containing version history for a model's prompts
 */
export interface PromptHistoryResponse {
  model_name: string;
  versions: PromptHistoryEntry[];
  total_versions: number;
}

/**
 * Response after restoring a prompt version
 */
export interface PromptRestoreResponse {
  model_name: string;
  restored_version: number;
  new_version: number;
  message: string;
}

/**
 * Response containing all prompt configurations for export
 */
export interface PromptExportResponse {
  exported_at: string;
  version: string;
  prompts: Record<string, Record<string, unknown>>;
}

/**
 * Response after importing prompt configurations
 */
export interface PromptImportResponse {
  imported_count: number;
  skipped_count: number;
  errors: string[];
  message: string;
}

/**
 * Fetch current prompt configurations for all AI models.
 *
 * @returns AllPromptsResponse containing all model configurations
 */
export async function fetchAllPrompts(): Promise<AllPromptsResponse> {
  return fetchApi<AllPromptsResponse>('/api/ai-audit/prompts');
}

/**
 * Fetch current prompt configuration for a specific AI model.
 *
 * @param model - Model name (nemotron, florence2, yolo_world, xclip, fashion_clip)
 * @returns ModelPromptResponse with current configuration
 */
export async function fetchModelPrompt(model: PromptModelName): Promise<ModelPromptResponse> {
  return fetchApi<ModelPromptResponse>(`/api/ai-audit/prompts/${model}`);
}

/**
 * Update prompt configuration for a specific AI model.
 *
 * @param model - Model name to update
 * @param config - New configuration for the model
 * @param description - Optional description of the changes
 * @returns PromptUpdateResponse with new version info
 */
export async function updateModelPrompt(
  model: PromptModelName,
  config: Record<string, unknown>,
  description?: string
): Promise<PromptUpdateResponse> {
  return fetchApi<PromptUpdateResponse>(`/api/ai-audit/prompts/${model}`, {
    method: 'PUT',
    body: JSON.stringify({ config, description }),
  });
}

/**
 * Test a modified prompt configuration against a specific event.
 *
 * @param model - Model name to test
 * @param config - Modified configuration to test
 * @param eventId - Event ID to test against
 * @returns PromptTestResponse with before/after comparison
 */
export async function testPrompt(
  model: PromptModelName,
  config: Record<string, unknown>,
  eventId: number
): Promise<PromptTestResponse> {
  return fetchApi<PromptTestResponse>('/api/ai-audit/prompts/test', {
    method: 'POST',
    body: JSON.stringify({ model, config, event_id: eventId }),
  });
}

/**
 * Fetch version history for all AI models.
 *
 * @param limit - Maximum number of versions to return per model (default 10)
 * @returns Dict mapping model names to their version histories
 */
export async function fetchAllPromptsHistory(
  limit: number = 10
): Promise<Record<string, PromptHistoryResponse>> {
  const queryParams = new URLSearchParams();
  queryParams.append('limit', String(limit));
  return fetchApi<Record<string, PromptHistoryResponse>>(
    `/api/ai-audit/prompts/history?${queryParams.toString()}`
  );
}

/**
 * Fetch version history for a specific AI model.
 *
 * @param model - Model name to get history for
 * @param limit - Maximum versions to return (default 50)
 * @param offset - Number of versions to skip (default 0)
 * @returns PromptHistoryResponse with version list
 */
export async function fetchModelHistory(
  model: PromptModelName,
  limit: number = 50,
  offset: number = 0
): Promise<PromptHistoryResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('limit', String(limit));
  queryParams.append('offset', String(offset));
  return fetchApi<PromptHistoryResponse>(
    `/api/ai-audit/prompts/history/${model}?${queryParams.toString()}`
  );
}

/**
 * Restore a specific version of a model's prompt configuration.
 *
 * @param model - Model name to restore version for
 * @param version - Version number to restore
 * @param description - Optional description for the restore action
 * @returns PromptRestoreResponse with restore details
 */
export async function restorePromptVersion(
  model: PromptModelName,
  version: number,
  description?: string
): Promise<PromptRestoreResponse> {
  const body = description ? { description } : {};
  return fetchApi<PromptRestoreResponse>(
    `/api/ai-audit/prompts/history/${version}?model=${model}`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    }
  );
}

/**
 * Export all AI model configurations as JSON.
 *
 * @returns PromptExportResponse with all configurations
 */
export async function exportPrompts(): Promise<PromptExportResponse> {
  return fetchApi<PromptExportResponse>('/api/ai-audit/prompts/export');
}

/**
 * Import AI model configurations from JSON.
 *
 * @param prompts - Model configurations to import
 * @param overwrite - Whether to overwrite existing configurations (default false)
 * @returns PromptImportResponse with import results
 */
export async function importPrompts(
  prompts: Record<string, Record<string, unknown>>,
  overwrite: boolean = false
): Promise<PromptImportResponse> {
  return fetchApi<PromptImportResponse>('/api/ai-audit/prompts/import', {
    method: 'POST',
    body: JSON.stringify({ prompts, overwrite }),
  });
}
