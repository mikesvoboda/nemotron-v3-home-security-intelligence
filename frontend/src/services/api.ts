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
  ExportJob,
  ExportJobCreateParams,
  ExportJobStartResponse,
  ExportJobListResponse,
  ExportJobCancelResponse,
  ExportDownloadInfo,
  ExportJobStatus,
  ExportType,
  ExportFormat,
} from '../types/export';

export type {
  AlertRule,
  AlertRuleCreate,
  AlertRuleListResponse,
  AlertRuleSchedule,
  AlertRuleUpdate,
  AlertSeverity,
  AuditLogListResponse,
  DayOfWeek,
  AuditLogResponse,
  AuditLogStats,
  Camera,
  CameraCreate,
  CameraListResponse,
  CameraPathValidationResponse,
  CameraUpdate,
  CameraValidationInfo,
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
  GPUStats,
  GPUStatsSample,
  GPUStatsHistoryResponse,
  HealthResponse,
  HTTPValidationError,
  MediaErrorResponse,
  PipelineLatencies,
  QueueDepths,
  ReadinessResponse,
  SearchResponse,
  SearchResult,
  ServiceStatus,
  ContainerServiceStatus,
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
  // Scene Change types
  SceneChangeListResponse,
  SceneChangeResponse,
  SceneChangeAcknowledgeResponse,
  // Pipeline Latency types
  PipelineLatencyResponse,
  PipelineLatencyHistoryResponse,
  PipelineStageLatency,
  LatencyHistorySnapshot,
  // Notification preferences types
  NotificationPreferencesResponse,
  NotificationPreferencesUpdate,
  CameraNotificationSettingResponse,
  CameraNotificationSettingUpdate,
  CameraNotificationSettingsListResponse,
  QuietHoursPeriodCreate,
  QuietHoursPeriodResponse,
  QuietHoursPeriodsListResponse,
} from '../types/generated';

import { addApiBreadcrumb, isSentryEnabled } from './sentry';
import { useRateLimitStore, type RateLimitInfo } from '../stores/rate-limit-store';

import type {
  CameraUptimeResponse,
  DetectionTrendsParams,
  DetectionTrendsResponse,
  ObjectDistributionResponse,
  RiskHistoryQueryParams,
  RiskHistoryResponse,
} from '../types/analytics';
import type {
  BulkOperationResponse,
  DetectionBulkCreateItem,
  DetectionBulkCreateResponse,
  DetectionBulkUpdateItem,
} from '../types/bulk';
import type {
  ExportJob,
  ExportJobCreateParams,
  ExportJobStartResponse,
  ExportJobListResponse,
  ExportJobCancelResponse,
  ExportDownloadInfo,
  ExportJobStatus,
} from '../types/export';
import type {
  AiAuditEventAuditResponse,
  AiAuditLeaderboardResponse,
  AiAuditRecommendationsResponse,
  AiAuditStatsResponse,
  AlertResponse,
  AlertRule,
  AlertRuleCreate,
  AlertRuleListResponse,
  AlertRuleUpdate,
  AlertSeverity,
  AlertStatus,
  AuditLogListResponse as GeneratedAuditLogListResponse,
  AuditLogResponse as GeneratedAuditLogResponse,
  AuditLogStats as GeneratedAuditLogStats,
  Camera,
  CameraCreate,
  CameraListResponse as GeneratedCameraListResponse,
  CameraPathValidationResponse,
  CameraUpdate,
  CircuitBreakerResetResponse as GeneratedCircuitBreakerResetResponse,
  CircuitBreakersResponse as GeneratedCircuitBreakersResponse,
  CleanupResponse,
  Detection as GeneratedDetection,
  DetectionListResponse as GeneratedDetectionListResponse,
  DetectionSearchResponse as GeneratedDetectionSearchResponse,
  DetectionLabelsResponse as GeneratedDetectionLabelsResponse,
  DLQClearResponse as GeneratedDLQClearResponse,
  DLQJobsResponse as GeneratedDLQJobsResponse,
  DLQRequeueResponse as GeneratedDLQRequeueResponse,
  DLQStatsResponse as GeneratedDLQStatsResponse,
  Event,
  EventClustersResponse,
  EventEnrichmentsResponse as GeneratedEventEnrichmentsResponse,
  EventListResponse as GeneratedEventListResponse,
  EventStatsResponse as GeneratedEventStatsResponse,
  GPUStats,
  GPUStatsHistoryResponse,
  HealthResponse,
  ReadinessResponse,
  SceneChangeAcknowledgeResponse,
  SceneChangeListResponse,
  PipelineLatencyResponse,
  PipelineLatencyHistoryResponse,
  PipelineStatusResponse,
  QueuesStatusResponse,
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
  NotificationPreferencesResponse,
  NotificationPreferencesUpdate,
  CameraNotificationSettingResponse,
  CameraNotificationSettingUpdate,
  CameraNotificationSettingsListResponse,
  QuietHoursPeriodCreate,
  QuietHoursPeriodResponse,
  QuietHoursPeriodsListResponse,
  EntityDetail,
  EntityListResponse,
  EntityHistoryResponse,
  EntityAppearance,
  EntitySummary,
  TrustStatus,
  EntityTrustUpdate,
  EntityTrustResponse,
  TrustedEntityListResponse,
  JobResponse,
  JobListResponse,
  JobStatusEnum,
  JobLogsResponse,
  JobLogEntryResponse,
  JobDetailResponse,
  JobHistoryResponse,
  JobTransitionResponse,
  JobSearchResponse,
  JobSearchAggregations,
  JobCancelResponse,
  JobAbortResponse,
  CleanupStatusResponse,
  OrphanedFileCleanupResponse,
  EventFeedbackCreate,
  EventFeedbackResponse,
  FeedbackType,
  FeedbackStatsResponse,
  ActualThreatLevel,
  CalibrationResponse,
  CalibrationUpdate,
  CalibrationDefaultsResponse,
  CalibrationResetResponse,
  RecordingResponse,
  RecordingsListResponse,
  ReplayResponse,
  EventRegistryResponse,
} from '../types/generated';
import type { SummariesLatestResponse } from '../types/summary';

// Re-export entity types for consumers of this module
export type {
  EntityAppearance,
  EntitySummary,
  EntityDetail,
  EntityListResponse,
  EntityHistoryResponse,
  TrustStatus,
  EntityTrustUpdate,
  EntityTrustResponse,
  TrustedEntityListResponse,
};

// Re-export job types for consumers of this module
export type {
  JobResponse,
  JobListResponse,
  JobStatusEnum,
  JobLogsResponse,
  JobLogEntryResponse,
  JobDetailResponse,
  JobHistoryResponse,
  JobTransitionResponse,
  JobSearchResponse,
  JobSearchAggregations,
  JobCancelResponse,
  JobAbortResponse,
  CleanupStatusResponse,
  OrphanedFileCleanupResponse,
};

// Re-export feedback types for consumers of this module
export type {
  EventFeedbackCreate,
  EventFeedbackResponse,
  FeedbackType,
  FeedbackStatsResponse,
  ActualThreatLevel,
};

// Re-export calibration types for consumers of this module
export type {
  CalibrationResponse,
  CalibrationUpdate,
  CalibrationDefaultsResponse,
  CalibrationResetResponse,
};

// Re-export alert types for consumers of this module
export type { AlertResponse, AlertStatus };

// Re-export enrichment types for consumers of this module
// Note: EnrichmentResponse is already defined in this file (see fetchDetectionEnrichment)
export type { EventEnrichmentsResponse } from '../types/generated';

// Re-export detection search and labels types for consumers of this module
export type {
  DetectionSearchResult,
  DetectionSearchResponse,
  DetectionLabelCount,
  DetectionLabelsResponse,
} from '../types/generated';

// Re-export analytics types for consumers of this module
export type {
  DetectionTrendsResponse,
  DetectionTrendsParams,
  DetectionTrendDataPoint,
  RiskHistoryResponse,
  RiskHistoryDataPoint,
  RiskHistoryQueryParams,
  CameraUptimeResponse,
  CameraUptimeDataPoint,
  ObjectDistributionResponse,
  ObjectDistributionDataPoint,
} from '../types/analytics';

// Re-export pipeline and system status types for consumers of this module
export type { PipelineStatusResponse, QueuesStatusResponse } from '../types/generated';

// Re-export event clustering types for consumers of this module (NEM-3676)
export type {
  EventClustersResponse,
  EventCluster,
  ClusterEventSummary,
  ClusterRiskLevels,
} from '../types/generated';

// Re-export WebSocket event discovery types (NEM-3639)
export type { EventRegistryResponse, EventTypeInfo } from '../types/generated';

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
  /**
   * Cursor for pagination. Pass the `next_cursor` value from the previous response.
   */
  cursor?: string;
}

/**
 * Valid values for ordering detections (NEM-3629).
 */
export type DetectionOrderBy = 'detected_at' | 'created_at';

/**
 * Query parameters for detection list endpoints.
 */
export interface DetectionQueryParams {
  limit?: number;
  /**
   * Cursor for pagination. Pass the `next_cursor` value from the previous response.
   */
  cursor?: string;
  /**
   * Order detections by: 'detected_at' (detection timestamp, default) or
   * 'created_at' (when associated with event - shows detection sequence in event).
   * NEM-3629: When using 'created_at', responses include association_created_at field.
   */
  order_detections_by?: DetectionOrderBy;
}

/**
 * Query parameters for event enrichments endpoint.
 */
export interface EventEnrichmentsQueryParams {
  /** Maximum number of enrichments to return (1-200, default 50) */
  limit?: number;
  /** Number of enrichments to skip (default 0) */
  offset?: number;
}

/**
 * Analysis stream event types for SSE streaming analysis (NEM-1665).
 */
export type AnalysisStreamEventType = 'progress' | 'complete' | 'error';

/**
 * Analysis stream event data structure for SSE streaming analysis.
 * Sent via Server-Sent Events during LLM inference.
 */
export interface AnalysisStreamEvent {
  /** Event type indicating the stage of analysis */
  event_type: AnalysisStreamEventType;
  /** Batch ID being analyzed */
  batch_id: string;
  /** Accumulated LLM response text (for progress events) */
  accumulated_text?: string;
  /** Final risk score (for complete events) */
  risk_score?: number;
  /** Risk level derived from score (for complete events) */
  risk_level?: string;
  /** Event ID created from analysis (for complete events) */
  event_id?: number;
  /** Summary text (for complete events) */
  summary?: string;
  /** Error code (for error events) */
  error_code?: string;
  /** Error message (for error events) */
  error_message?: string;
  /** Whether the error is recoverable (for error events) */
  recoverable?: boolean;
}

// ============================================================================
// Cursor Validation (NEM-2585)
// ============================================================================

/**
 * Regular expression pattern for valid cursor format.
 * Cursors are base64url-encoded strings (RFC 4648) that may contain:
 * - Alphanumeric characters (a-z, A-Z, 0-9)
 * - URL-safe characters: underscore (_) and hyphen (-)
 * - Padding character: equals (=)
 *
 * This pattern validates the cursor format before sending to the API
 * to prevent injection attacks and malformed requests.
 */
const CURSOR_FORMAT_REGEX = /^[a-zA-Z0-9_=-]+$/;

/**
 * Maximum allowed cursor length to prevent DoS via oversized cursors.
 * Base64-encoded JSON payload {"id": <int>, "created_at": "<ISO8601>"}
 * should not exceed 200 characters in normal operation.
 */
const MAX_CURSOR_LENGTH = 500;

/**
 * Error thrown when cursor validation fails.
 * Contains the invalid cursor value and reason for failure.
 */
export class CursorValidationError extends Error {
  constructor(
    public readonly cursor: string,
    public readonly reason: string
  ) {
    super(`Invalid cursor: ${reason}`);
    this.name = 'CursorValidationError';
  }
}

/**
 * Validates the format of a pagination cursor before sending to the API.
 *
 * Cursors must be:
 * - Base64url-encoded (alphanumeric, underscore, hyphen, equals)
 * - Not exceed maximum length (prevent DoS)
 * - Non-empty if provided
 *
 * @param cursor - The cursor string to validate, or undefined/null
 * @returns true if the cursor is valid or not provided
 * @throws CursorValidationError if the cursor format is invalid
 *
 * @example
 * ```typescript
 * // Valid cursors
 * validateCursorFormat(undefined); // true (no cursor)
 * validateCursorFormat('eyJpZCI6MTIzfQ=='); // true (valid base64url)
 *
 * // Invalid cursors
 * validateCursorFormat('<script>'); // throws CursorValidationError
 * validateCursorFormat('a'.repeat(1000)); // throws CursorValidationError
 * ```
 */
export function validateCursorFormat(cursor: string | undefined | null): boolean {
  // No cursor is valid (first page or no pagination)
  if (cursor === undefined || cursor === null || cursor === '') {
    return true;
  }

  // Check for maximum length to prevent DoS
  if (cursor.length > MAX_CURSOR_LENGTH) {
    throw new CursorValidationError(
      cursor.substring(0, 50) + '...',
      `cursor exceeds maximum length of ${MAX_CURSOR_LENGTH} characters`
    );
  }

  // Check for valid base64url format
  if (!CURSOR_FORMAT_REGEX.test(cursor)) {
    throw new CursorValidationError(
      cursor.substring(0, 50),
      'cursor contains invalid characters (must be base64url-encoded)'
    );
  }

  return true;
}

/**
 * Type guard to check if a cursor is valid without throwing.
 * Useful for conditional logic where you want to handle invalid cursors gracefully.
 *
 * @param cursor - The cursor string to validate
 * @returns true if the cursor is valid or not provided, false otherwise
 */
export function isValidCursor(cursor: string | undefined | null): boolean {
  try {
    return validateCursorFormat(cursor);
  } catch {
    return false;
  }
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * RFC 7807 Problem Details interface for standardized API error responses.
 * @see https://tools.ietf.org/html/rfc7807
 */
export interface ProblemDetails {
  /**
   * A URI reference that identifies the problem type.
   * When this member is not present, its value is assumed to be "about:blank".
   */
  type: string;

  /**
   * A short, human-readable summary of the problem type.
   * It should NOT change from occurrence to occurrence.
   */
  title: string;

  /**
   * The HTTP status code generated by the origin server.
   */
  status: number;

  /**
   * A human-readable explanation specific to this occurrence of the problem.
   */
  detail?: string;

  /**
   * A URI reference that identifies the specific occurrence of the problem.
   * Typically the request path.
   */
  instance?: string;

  /**
   * Additional extension members not defined by RFC 7807.
   * Allows for custom error properties from the backend.
   */
  [key: string]: unknown;
}

/**
 * Type guard to check if an object is a valid RFC 7807 ProblemDetails response.
 * Validates the presence of required fields: type, title, and status.
 *
 * @param obj - The object to check
 * @returns true if the object conforms to RFC 7807 ProblemDetails
 */
export function isProblemDetails(obj: unknown): obj is ProblemDetails {
  if (typeof obj !== 'object' || obj === null) {
    return false;
  }

  const candidate = obj as Record<string, unknown>;

  return (
    typeof candidate.type === 'string' &&
    typeof candidate.title === 'string' &&
    typeof candidate.status === 'number'
  );
}

/**
 * API Error class with support for RFC 7807 Problem Details.
 *
 * When the backend returns an RFC 7807 error response, the full problem details
 * are available via the `problemDetails` property. For backward compatibility,
 * the `message` property is set to the detail or title field.
 */
export class ApiError extends Error {
  /**
   * RFC 7807 Problem Details object, if the error response conforms to the spec.
   * This provides access to all RFC 7807 fields: type, title, status, detail, instance.
   */
  public readonly problemDetails?: ProblemDetails;

  constructor(
    public status: number,
    message: string,
    public data?: unknown,
    problemDetails?: ProblemDetails
  ) {
    super(message);
    this.name = 'ApiError';
    this.problemDetails = problemDetails;
  }

  /**
   * Convenience getter for the RFC 7807 type field.
   * Returns "about:blank" if not a Problem Details error.
   */
  get type(): string {
    return this.problemDetails?.type ?? 'about:blank';
  }

  /**
   * Convenience getter for the RFC 7807 title field.
   * Returns the error message if not a Problem Details error.
   */
  get title(): string {
    return this.problemDetails?.title ?? this.message;
  }

  /**
   * Convenience getter for the RFC 7807 detail field.
   * Returns the error message if not a Problem Details error.
   */
  get detail(): string | undefined {
    return this.problemDetails?.detail ?? this.message;
  }

  /**
   * Convenience getter for the RFC 7807 instance field.
   * Returns undefined if not a Problem Details error.
   */
  get instance(): string | undefined {
    return this.problemDetails?.instance;
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
  /** Optional timeout in milliseconds. Defaults to DEFAULT_TIMEOUT_MS */
  timeout?: number;
}

// ============================================================================
// Timeout Error Handling
// ============================================================================

/**
 * Default timeout for fetch requests in milliseconds.
 * 30 seconds is a reasonable default for most API calls.
 */
export const DEFAULT_TIMEOUT_MS = 30000;

/**
 * Error class for request timeouts.
 * Thrown when a fetch request exceeds the specified timeout duration.
 */
export class TimeoutError extends Error {
  /** The timeout duration in milliseconds */
  public readonly timeout: number;

  constructor(timeout: number) {
    super(`Request timed out after ${timeout}ms`);
    this.name = 'TimeoutError';
    this.timeout = timeout;
  }
}

/**
 * Check if an error is a TimeoutError (request exceeded timeout).
 * Used to distinguish timeouts from other errors for specific handling.
 *
 * @param error - The error to check
 * @returns true if the error is a TimeoutError
 */
export function isTimeoutError(error: unknown): boolean {
  if (error instanceof TimeoutError) {
    return true;
  }
  if (error instanceof Error && error.name === 'TimeoutError') {
    return true;
  }
  return false;
}

/**
 * Combines multiple AbortSignals into a single signal that aborts
 * when any of the input signals abort.
 *
 * This is useful for combining user-provided abort signals with
 * internal timeout signals, ensuring both cancellation methods work.
 *
 * @param signals - Array of AbortSignals to combine
 * @returns A new AbortSignal that aborts when any input signal aborts
 *
 * @example
 * ```typescript
 * const userController = new AbortController();
 * const timeoutController = new AbortController();
 *
 * // This signal will abort if either the user cancels or timeout occurs
 * const combined = anySignal([userController.signal, timeoutController.signal]);
 *
 * fetch('/api/data', { signal: combined });
 * ```
 */
export function anySignal(signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController();

  // Check if any signal is already aborted
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
  }

  // Listen for abort on each signal
  for (const signal of signals) {
    signal.addEventListener(
      'abort',
      () => {
        if (!controller.signal.aborted) {
          controller.abort(signal.reason);
        }
      },
      { once: true }
    );
  }

  return controller.signal;
}

/**
 * Extended fetch options that include timeout configuration.
 */
export interface FetchWithTimeoutOptions extends Omit<RequestInit, 'signal'> {
  /**
   * Timeout in milliseconds. After this duration, the request will be aborted
   * and a TimeoutError will be thrown. Defaults to DEFAULT_TIMEOUT_MS (30000ms).
   * Set to 0 to use the default timeout.
   */
  timeout?: number;

  /**
   * External AbortSignal for user-controlled cancellation.
   * This signal is combined with the internal timeout signal.
   */
  signal?: AbortSignal;
}

/**
 * Performs a fetch request with automatic timeout support using AbortController.
 *
 * This function wraps the native fetch API to add timeout functionality. When
 * the timeout is reached, the request is aborted and a TimeoutError is thrown.
 *
 * If an external signal is provided, it is combined with the timeout signal
 * using anySignal, allowing both user cancellation and timeout to work.
 *
 * @param url - The URL to fetch
 * @param options - Fetch options including timeout and optional external signal
 * @returns Promise resolving to the Response
 * @throws TimeoutError if the request exceeds the timeout
 * @throws DOMException (AbortError) if the external signal is aborted
 *
 * @example
 * ```typescript
 * // Basic usage with timeout
 * const response = await fetchWithTimeout('/api/data', { timeout: 5000 });
 *
 * // With external abort controller (e.g., for React cleanup)
 * const controller = new AbortController();
 * const response = await fetchWithTimeout('/api/data', {
 *   timeout: 5000,
 *   signal: controller.signal,
 * });
 *
 * // In cleanup: controller.abort();
 * ```
 */
export async function fetchWithTimeout(
  url: string,
  options: FetchWithTimeoutOptions = {}
): Promise<Response> {
  const { timeout = DEFAULT_TIMEOUT_MS, signal: externalSignal, ...fetchOptions } = options;

  // Use default timeout if 0 is passed (treat 0 as "use default")
  const effectiveTimeout = timeout > 0 ? timeout : DEFAULT_TIMEOUT_MS;

  const timeoutController = new AbortController();
  let timedOut = false;

  const timeoutId = setTimeout(() => {
    timedOut = true;
    // Don't pass an error to abort() to avoid unhandled rejections
    // We'll check timedOut flag and throw TimeoutError from the catch block
    timeoutController.abort();
  }, effectiveTimeout);

  // Combine external signal with timeout signal if provided
  const combinedSignal = externalSignal
    ? anySignal([externalSignal, timeoutController.signal])
    : timeoutController.signal;

  try {
    const response = await fetch(url, { ...fetchOptions, signal: combinedSignal });
    return response;
  } catch (error) {
    // Check if this was a timeout abort
    if (error instanceof DOMException && error.name === 'AbortError' && timedOut) {
      throw new TimeoutError(effectiveTimeout);
    }
    // Re-throw other errors (including user-initiated AbortErrors)
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
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

/**
 * Extracts rate limit information from response headers.
 *
 * Looks for standard rate limit headers:
 * - `X-RateLimit-Limit`: Maximum requests allowed per window
 * - `X-RateLimit-Remaining`: Remaining requests in current window
 * - `X-RateLimit-Reset`: Unix timestamp when rate limit resets
 * - `Retry-After`: Seconds until retry is allowed (optional, typically on 429)
 *
 * @param response - The fetch Response object
 * @returns RateLimitInfo object if all required headers are present and valid, null otherwise
 *
 * @example
 * ```typescript
 * const response = await fetch('/api/endpoint');
 * const rateLimitInfo = extractRateLimitInfo(response);
 * if (rateLimitInfo) {
 *   console.log(`${rateLimitInfo.remaining}/${rateLimitInfo.limit} requests remaining`);
 * }
 * ```
 */
export function extractRateLimitInfo(response: Response): RateLimitInfo | null {
  const limitHeader = response.headers.get('X-RateLimit-Limit');
  const remainingHeader = response.headers.get('X-RateLimit-Remaining');
  const resetHeader = response.headers.get('X-RateLimit-Reset');
  const retryAfterHeader = response.headers.get('Retry-After');

  // All three required headers must be present
  if (!limitHeader || !remainingHeader || !resetHeader) {
    return null;
  }

  const limit = parseInt(limitHeader, 10);
  const remaining = parseInt(remainingHeader, 10);
  const reset = parseInt(resetHeader, 10);

  // Validate that parsing produced valid numbers
  if (isNaN(limit) || isNaN(remaining) || isNaN(reset)) {
    return null;
  }

  const info: RateLimitInfo = {
    limit,
    remaining,
    reset,
  };

  // Add retryAfter if header is present and valid
  if (retryAfterHeader) {
    const retryAfter = parseInt(retryAfterHeader, 10);
    if (!isNaN(retryAfter)) {
      info.retryAfter = retryAfter;
    }
  }

  return info;
}

/**
 * Adds a Sentry breadcrumb for an API request if Sentry is enabled.
 * This provides request tracking for debugging errors.
 *
 * @param method - HTTP method (GET, POST, etc.)
 * @param url - Full request URL
 * @param status - Response status code
 * @param duration - Request duration in milliseconds
 */
function addSentryBreadcrumb(method: string, url: string, status: number, duration: number): void {
  if (isSentryEnabled()) {
    addApiBreadcrumb(method, url, status, duration);
  }
}

/**
 * Parses an error response body and extracts error information.
 * Supports RFC 7807 Problem Details format as well as legacy error formats.
 *
 * @param errorBody - The parsed JSON body of an error response
 * @param defaultMessage - Default message to use if none can be extracted
 * @returns An object containing the error message, data, and optional ProblemDetails
 */
function parseErrorBody(
  errorBody: unknown,
  defaultMessage: string
): { message: string; data: unknown; problemDetails?: ProblemDetails } {
  // Check if it's an RFC 7807 Problem Details response
  if (isProblemDetails(errorBody)) {
    // Use detail if available, otherwise fall back to title
    const message = errorBody.detail ?? errorBody.title;
    return {
      message,
      data: errorBody,
      problemDetails: errorBody,
    };
  }

  // Legacy format: { detail: string }
  if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
    return {
      message: String((errorBody as { detail: unknown }).detail),
      data: errorBody,
    };
  }

  // Plain string error
  if (typeof errorBody === 'string') {
    return {
      message: errorBody,
      data: undefined,
    };
  }

  // Unknown format - use default message and store body as data
  return {
    message: defaultMessage,
    data: errorBody,
  };
}

async function handleResponse<T>(response: Response): Promise<T> {
  // Extract rate limit info from headers and update global store
  const rateLimitInfo = extractRateLimitInfo(response);
  if (rateLimitInfo) {
    useRateLimitStore.getState().update(rateLimitInfo);
  }

  if (!response.ok) {
    const defaultMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorMessage = defaultMessage;
    let errorData: unknown = undefined;
    let problemDetails: ProblemDetails | undefined = undefined;

    try {
      const errorBody: unknown = await response.json();
      const parsed = parseErrorBody(errorBody, defaultMessage);
      errorMessage = parsed.message;
      errorData = parsed.data;
      problemDetails = parsed.problemDetails;
    } catch {
      // If response body is not JSON, use status text
    }

    // For 429 Too Many Requests, include retry_after in error data if available
    if (response.status === 429) {
      const retryAfterHeader = response.headers.get('Retry-After');
      if (retryAfterHeader) {
        const retryAfter = parseInt(retryAfterHeader, 10);
        if (!isNaN(retryAfter)) {
          // Merge retry_after into error data
          errorData =
            typeof errorData === 'object' && errorData !== null
              ? { ...errorData, retry_after: retryAfter }
              : { retry_after: retryAfter };
        }
      }
    }

    throw new ApiError(response.status, errorMessage, errorData, problemDetails);
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
 * Adds Sentry breadcrumbs for request tracking.
 * @param url - Full URL to fetch
 * @param options - Fetch options
 * @param retriesLeft - Number of retries remaining
 */
async function fetchWithRetry<T>(
  url: string,
  options: RequestInit,
  retriesLeft: number = MAX_RETRIES
): Promise<T> {
  const startTime = Date.now();
  const method = options.method || 'GET';

  // Convert RequestInit to FetchWithTimeoutOptions (null signal becomes undefined)
  const { signal, ...restOptions } = options;
  const timeoutOptions: FetchWithTimeoutOptions = {
    ...restOptions,
    ...(signal && { signal }),
  };

  try {
    const response = await fetchWithTimeout(url, timeoutOptions);
    const duration = Date.now() - startTime;

    // Add Sentry breadcrumb for the request
    addSentryBreadcrumb(method, url, response.status, duration);

    // Check if we should retry based on status code
    if (!response.ok && shouldRetry(response.status) && retriesLeft > 0) {
      const delay = getRetryDelay(MAX_RETRIES - retriesLeft);
      await sleep(delay);
      return fetchWithRetry<T>(url, options, retriesLeft - 1);
    }

    return handleResponse<T>(response);
  } catch (error) {
    const duration = Date.now() - startTime;

    // Re-throw AbortError without wrapping - request was intentionally cancelled
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw error;
    }

    // For TimeoutErrors, retry if we have retries left
    if (isTimeoutError(error)) {
      addSentryBreadcrumb(method, url, 0, duration);

      if (retriesLeft > 0) {
        const delay = getRetryDelay(MAX_RETRIES - retriesLeft);
        await sleep(delay);
        return fetchWithRetry<T>(url, options, retriesLeft - 1);
      }
      // After all retries, throw as ApiError for consistent error handling
      throw new ApiError(0, error instanceof Error ? error.message : 'Request timed out');
    }

    // For ApiErrors that are retryable, retry
    if (error instanceof ApiError) {
      // Add breadcrumb for the failed request
      addSentryBreadcrumb(method, url, error.status, duration);

      if (shouldRetry(error.status) && retriesLeft > 0) {
        const delay = getRetryDelay(MAX_RETRIES - retriesLeft);
        await sleep(delay);
        return fetchWithRetry<T>(url, options, retriesLeft - 1);
      }
      throw error;
    }

    // Network errors - add breadcrumb with status 0
    addSentryBreadcrumb(method, url, 0, duration);

    // Network errors - retry if we have retries left
    if (retriesLeft > 0) {
      const delay = getRetryDelay(MAX_RETRIES - retriesLeft);
      await sleep(delay);
      return fetchWithRetry<T>(url, options, retriesLeft - 1);
    }

    throw new ApiError(0, error instanceof Error ? error.message : 'Network request failed');
  }
}

export async function fetchApi<T>(endpoint: string, options?: FetchOptions): Promise<T> {
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

/**
 * Fetch all cameras.
 *
 * @param options - Optional fetch options including AbortSignal for cancellation (NEM-3411)
 * @returns Array of Camera objects
 */
export async function fetchCameras(options?: { signal?: AbortSignal }): Promise<Camera[]> {
  const response = await fetchApi<GeneratedCameraListResponse>('/api/cameras', options);
  return response.items;
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
 * Fetch all soft-deleted cameras (trash view).
 *
 * Returns cameras that have been soft-deleted (deleted_at is not null),
 * ordered by deleted_at descending (most recently deleted first).
 *
 * @returns Array of soft-deleted Camera objects
 */
export async function fetchDeletedCameras(): Promise<Camera[]> {
  const response = await fetchApi<GeneratedCameraListResponse>('/api/cameras/deleted');
  return response.items;
}

/**
 * Restore a soft-deleted camera.
 *
 * Clears the deleted_at timestamp on a soft-deleted camera, making it
 * visible again in normal queries.
 *
 * @param id - The camera ID to restore
 * @returns The restored Camera object
 * @throws ApiError if camera not found (404) or not deleted (400)
 */
export async function restoreCamera(id: string): Promise<Camera> {
  return fetchApi<Camera>(`/api/cameras/${id}/restore`, {
    method: 'POST',
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
// Camera Path Validation Endpoint (NEM-3578)
// ============================================================================

/**
 * Fetch camera path validation results for all cameras.
 *
 * This endpoint validates all camera folder paths against the configured base path,
 * checking whether directories exist, contain files, and are properly configured.
 *
 * Useful for diagnostics when cameras show "No snapshot available" errors.
 *
 * @returns CameraPathValidationResponse with validation results for all cameras
 *
 * @example
 * ```typescript
 * const validation = await fetchCameraPathValidation();
 * console.log(`Valid: ${validation.valid_count}, Invalid: ${validation.invalid_count}`);
 *
 * // Show cameras with issues
 * validation.invalid_cameras.forEach(cam => {
 *   console.log(`${cam.name}: ${cam.issues?.join(', ')}`);
 * });
 * ```
 */
export async function fetchCameraPathValidation(): Promise<CameraPathValidationResponse> {
  return fetchApi<CameraPathValidationResponse>('/api/cameras/validation/paths');
}

// ============================================================================
// Camera Snapshot Status Helper (NEM-3579)
// ============================================================================

/**
 * Snapshot status information returned by checkCameraSnapshot.
 */
export interface CameraSnapshotStatus {
  /** Whether the snapshot is available */
  available: boolean;
  /** The snapshot URL if available */
  url: string;
  /** Error message if snapshot is not available */
  error?: string;
  /** Error code from the API (e.g., 404) */
  errorCode?: number;
  /** Suggested action to resolve the issue */
  suggestion?: string;
}

/**
 * Check if a camera snapshot is available.
 *
 * This helper performs a HEAD request to the snapshot endpoint to check availability
 * without downloading the full image. Provides detailed error information and
 * suggestions for troubleshooting when snapshots are unavailable.
 *
 * @param cameraId - The camera ID to check
 * @returns CameraSnapshotStatus with availability and error details
 *
 * @example
 * ```typescript
 * const status = await checkCameraSnapshot('front_door');
 * if (status.available) {
 *   // Use status.url in an <img> tag
 *   return <img src={status.url} alt="Camera snapshot" />;
 * } else {
 *   // Show error message with suggestion
 *   return (
 *     <div>
 *       <p>Snapshot unavailable: {status.error}</p>
 *       <p>{status.suggestion}</p>
 *     </div>
 *   );
 * }
 * ```
 */
export async function checkCameraSnapshot(cameraId: string): Promise<CameraSnapshotStatus> {
  const url = getCameraSnapshotUrl(cameraId);

  try {
    // Use HEAD request to check availability without downloading
    const response = await fetch(url, {
      method: 'HEAD',
      // Snapshot endpoints are exempt from API key auth
    });

    if (response.ok) {
      return {
        available: true,
        url,
      };
    }

    // Handle specific error codes with helpful suggestions
    let error = 'Snapshot unavailable';
    let suggestion = 'Check camera configuration';

    if (response.status === 404) {
      // Try to parse error response for more details
      // Note: HEAD requests don't have bodies, so we'll provide generic suggestions
      error = 'Camera folder or snapshot not found';
      suggestion =
        'Verify the camera folder exists and contains image or video files. ' +
        'Use the path validation endpoint to diagnose issues.';
    } else if (response.status === 429) {
      error = 'Too many requests';
      suggestion = 'Wait a moment before trying again.';
    } else if (response.status === 500) {
      error = 'Server error while processing snapshot';
      suggestion = 'Check server logs for details. Video frame extraction may have failed.';
    }

    return {
      available: false,
      url,
      error,
      errorCode: response.status,
      suggestion,
    };
  } catch (err) {
    // Network error or other fetch failure
    return {
      available: false,
      url,
      error: err instanceof Error ? err.message : 'Network error',
      suggestion: 'Check your network connection and ensure the backend is running.',
    };
  }
}

/**
 * Fetch a camera snapshot as a blob.
 *
 * This function downloads the snapshot image and returns it as a Blob,
 * useful for displaying in canvas elements or processing the image data.
 *
 * @param cameraId - The camera ID to fetch snapshot for
 * @returns Promise resolving to the image Blob
 * @throws ApiError if the snapshot is not available
 *
 * @example
 * ```typescript
 * try {
 *   const blob = await fetchCameraSnapshot('front_door');
 *   const imageUrl = URL.createObjectURL(blob);
 *   // Use imageUrl in an <img> tag or canvas
 * } catch (error) {
 *   console.error('Failed to fetch snapshot:', error);
 * }
 * ```
 */
export async function fetchCameraSnapshot(cameraId: string): Promise<Blob> {
  const url = getCameraSnapshotUrl(cameraId);
  const response = await fetch(url);

  if (!response.ok) {
    throw new ApiError(response.status, `Failed to fetch snapshot for camera ${cameraId}`);
  }

  return response.blob();
}

// ============================================================================
// Baseline Analytics Types (manual definitions until regenerated)
// ============================================================================

/**
 * A single activity baseline entry for a specific hour and day combination.
 * Represents one cell in the 24x7 activity heatmap.
 */
export interface ActivityBaselineEntry {
  /** Hour of day (0-23) */
  hour: number;
  /** Day of week (0=Monday, 6=Sunday) */
  day_of_week: number;
  /** Average activity count for this time slot */
  avg_count: number;
  /** Number of samples used to calculate this average */
  sample_count: number;
  /** Whether this time slot has above-average activity */
  is_peak: boolean;
}

/**
 * Response for camera activity baseline endpoint.
 */
export interface ActivityBaselineResponse {
  /** Camera ID */
  camera_id: string;
  /** Activity baseline entries (up to 168 = 24h x 7 days) */
  entries: ActivityBaselineEntry[];
  /** Total number of samples across all entries */
  total_samples: number;
  /** Hour with highest average activity (0-23), null if no data */
  peak_hour: number | null;
  /** Day with highest average activity (0=Monday, 6=Sunday), null if no data */
  peak_day: number | null;
  /** Whether baseline has sufficient samples for reliable anomaly detection */
  learning_complete: boolean;
  /** Minimum samples required per time slot for learning completion */
  min_samples_required: number;
}

/**
 * Baseline entry for a specific object class at a specific hour.
 */
export interface ClassBaselineEntry {
  /** Object class (e.g., person, vehicle, animal) */
  object_class: string;
  /** Hour of day (0-23) */
  hour: number;
  /** Frequency of this class at this hour */
  frequency: number;
  /** Number of samples for this class/hour combination */
  sample_count: number;
}

/**
 * Response for camera class frequency baseline endpoint.
 */
export interface ClassBaselineResponse {
  /** Camera ID */
  camera_id: string;
  /** Class baseline entries grouped by class and hour */
  entries: ClassBaselineEntry[];
  /** List of unique object classes detected for this camera */
  unique_classes: string[];
  /** Total number of samples across all entries */
  total_samples: number;
  /** Most frequently detected object class, null if no data */
  most_common_class: string | null;
}

/**
 * Current anomaly detection configuration.
 */
export interface AnomalyConfig {
  /** Number of standard deviations from mean for anomaly detection */
  threshold_stdev: number;
  /** Minimum samples required before anomaly detection is reliable */
  min_samples: number;
  /** Exponential decay factor for EWMA (0 < factor <= 1) */
  decay_factor: number;
  /** Rolling window size in days for baseline calculations */
  window_days: number;
}

/**
 * Request to update anomaly detection configuration.
 */
export interface AnomalyConfigUpdate {
  /** Number of standard deviations from mean for anomaly detection */
  threshold_stdev?: number;
  /** Minimum samples required before anomaly detection is reliable */
  min_samples?: number;
}

/**
 * Human-readable interpretation of deviation from baseline.
 * Used to categorize how much current activity deviates from established patterns.
 */
export type DeviationInterpretation =
  | 'far_below_normal'
  | 'below_normal'
  | 'normal'
  | 'slightly_above_normal'
  | 'above_normal'
  | 'far_above_normal';

/**
 * Current deviation status from baseline.
 */
export interface CurrentDeviation {
  /** Deviation score (standard deviations from mean, can be negative) */
  score: number;
  /** Human-readable interpretation of the deviation */
  interpretation: DeviationInterpretation;
  /** Factors contributing to current deviation */
  contributing_factors: string[];
}

/**
 * Hourly activity pattern statistics.
 * Matches backend HourlyPattern schema.
 */
export interface HourlyPattern {
  /** Average number of detections during this hour */
  avg_detections: number;
  /** Number of samples used for this calculation */
  sample_count: number;
  /** Standard deviation of detection count */
  std_dev: number;
}

/**
 * Daily activity pattern statistics.
 * Matches backend DailyPattern schema.
 */
export interface DailyPattern {
  /** Average number of detections for this day */
  avg_detections: number;
  /** Hour with most activity (0-23) */
  peak_hour: number;
  /** Total samples for this day */
  total_samples: number;
}

/**
 * Object-specific baseline statistics.
 * Matches backend ObjectBaseline schema.
 */
export interface ObjectBaseline {
  /** Average hourly detection count for this object type */
  avg_hourly: number;
  /** Hour with most detections of this type (0-23) */
  peak_hour: number;
  /** Total detections of this type in the baseline period */
  total_detections: number;
}

/**
 * Comprehensive baseline summary response for a camera.
 * Contains activity patterns, object baselines, and current deviation status.
 */
export interface BaselineSummaryResponse {
  /** Camera ID */
  camera_id: string;
  /** Human-readable camera name */
  camera_name: string;
  /** Total number of data points in baseline */
  data_points: number;
  /** When baseline data collection started (null if no data) */
  baseline_established: string | null;
  /** Current deviation from baseline (null if insufficient data) */
  current_deviation: CurrentDeviation | null;
  /** Activity patterns by hour (0-23) */
  hourly_patterns?: Record<string, HourlyPattern>;
  /** Activity patterns by day of week (monday-sunday) */
  daily_patterns?: Record<string, DailyPattern>;
  /** Baseline statistics by object type */
  object_baselines?: Record<string, ObjectBaseline>;
}

/**
 * A single anomaly event detected for a camera.
 * Represents activity that significantly deviated from established baseline patterns.
 */
export interface CameraAnomalyEvent {
  /** When the anomaly was detected */
  timestamp: string;
  /** Object class that triggered the anomaly */
  detection_class: string;
  /** Anomaly score (0.0-1.0, higher is more anomalous) */
  anomaly_score: number;
  /** Expected frequency for this class at this time */
  expected_frequency: number;
  /** Observed frequency that triggered the anomaly */
  observed_frequency: number;
  /** Human-readable explanation of why this is anomalous */
  reason: string;
}

/**
 * Response for camera anomaly list endpoint.
 */
export interface CameraAnomaliesResponse {
  /** Camera ID */
  camera_id: string;
  /** Number of days covered by this query */
  period_days: number;
  /** Total number of anomalies returned */
  count: number;
  /** List of recent anomaly events */
  anomalies: CameraAnomalyEvent[];
}

// ============================================================================
// Baseline Analytics Endpoints
// ============================================================================

/**
 * Fetch activity baseline data for a camera.
 * Returns up to 168 entries (24 hours x 7 days) representing the full weekly
 * activity heatmap.
 *
 * @param cameraId - Camera ID
 * @returns ActivityBaselineResponse with entries for the heatmap
 */
export async function fetchCameraActivityBaseline(
  cameraId: string
): Promise<ActivityBaselineResponse> {
  return fetchApi<ActivityBaselineResponse>(
    `/api/cameras/${encodeURIComponent(cameraId)}/baseline/activity`
  );
}

/**
 * Fetch class frequency baseline data for a camera.
 * Returns baseline entries grouped by object class and hour.
 *
 * @param cameraId - Camera ID
 * @returns ClassBaselineResponse with entries for each class/hour combination
 */
export async function fetchCameraClassBaseline(cameraId: string): Promise<ClassBaselineResponse> {
  return fetchApi<ClassBaselineResponse>(
    `/api/cameras/${encodeURIComponent(cameraId)}/baseline/classes`
  );
}

/**
 * Fetch comprehensive baseline summary for a camera.
 * Returns activity patterns, object baselines, and current deviation status.
 *
 * @param cameraId - Camera ID
 * @returns BaselineSummaryResponse with all baseline data
 */
export async function fetchCameraBaseline(cameraId: string): Promise<BaselineSummaryResponse> {
  return fetchApi<BaselineSummaryResponse>(
    `/api/cameras/${encodeURIComponent(cameraId)}/baseline`
  );
}

/**
 * Fetch anomaly events for a camera.
 * Returns recent activity that deviated significantly from established baseline patterns.
 *
 * @param cameraId - Camera ID
 * @param days - Number of days to look back for anomalies (default: 7)
 * @returns CameraAnomaliesResponse with list of anomaly events
 */
export async function fetchCameraAnomalies(
  cameraId: string,
  days: number = 7
): Promise<CameraAnomaliesResponse> {
  return fetchApi<CameraAnomaliesResponse>(
    `/api/cameras/${encodeURIComponent(cameraId)}/anomalies?days=${days}`
  );
}

/**
 * Fetch current anomaly detection configuration.
 *
 * @returns AnomalyConfig with current anomaly detection settings
 */
export async function fetchAnomalyConfig(): Promise<AnomalyConfig> {
  return fetchApi<AnomalyConfig>('/api/system/anomaly-config');
}

/**
 * Update anomaly detection configuration.
 *
 * @param config - Configuration values to update (only provided values are changed)
 * @returns AnomalyConfig with updated settings
 */
export async function updateAnomalyConfig(config: AnomalyConfigUpdate): Promise<AnomalyConfig> {
  return fetchApi<AnomalyConfig>('/api/system/anomaly-config', {
    method: 'PATCH',
    body: JSON.stringify(config),
  });
}

// ============================================================================
// System Endpoints
// ============================================================================

/**
 * Fetch system health status.
 *
 * @param options - Optional fetch options including AbortSignal for cancellation (NEM-3411)
 * @returns HealthResponse with service status information
 *
 * @example
 * ```typescript
 * // Basic usage
 * const health = await fetchHealth();
 *
 * // With AbortSignal for cancellation
 * const controller = new AbortController();
 * const health = await fetchHealth({ signal: controller.signal });
 * ```
 */
export async function fetchHealth(options?: { signal?: AbortSignal }): Promise<HealthResponse> {
  return fetchApi<HealthResponse>('/api/system/health', options);
}

// ============================================================================
// Full Health Check Types (NEM-1582)
// These types should be moved to generated types after running generate-types.sh
// ============================================================================

/** Health state for a service */
export type ServiceHealthState = 'healthy' | 'unhealthy' | 'degraded' | 'unknown';

/** Circuit breaker state */
export type CircuitStateEnum = 'closed' | 'open' | 'half_open';

/** Health status for an individual AI service */
export interface AIServiceHealthStatus {
  name: string;
  display_name: string;
  status: ServiceHealthState;
  url: string;
  response_time_ms: number | null;
  error: string | null;
  circuit_state: CircuitStateEnum;
  last_check: string | null;
}

/** Health status for infrastructure services (database, redis) */
export interface InfrastructureHealthStatus {
  name: string;
  status: ServiceHealthState;
  message: string | null;
  details: Record<string, unknown> | null;
}

/** Summary of circuit breaker states */
export interface CircuitBreakerSummary {
  total: number;
  open: number;
  half_open: number;
  closed: number;
  breakers: Record<string, CircuitStateEnum>;
}

/** Health status for a background worker */
export interface WorkerHealthStatusFull {
  name: string;
  running: boolean;
  critical: boolean;
  message: string | null;
}

/** Comprehensive health status for all system components */
export interface FullHealthResponse {
  status: ServiceHealthState;
  ready: boolean;
  message: string;
  postgres: InfrastructureHealthStatus;
  redis: InfrastructureHealthStatus;
  ai_services: AIServiceHealthStatus[];
  circuit_breakers: CircuitBreakerSummary;
  workers: WorkerHealthStatusFull[];
  timestamp: string;
  version: string;
}

/**
 * Fetch comprehensive system health including all AI services and circuit breakers.
 * Returns 503 if critical services are unhealthy.
 *
 * @param options - Optional fetch options including AbortSignal for cancellation (NEM-3411)
 * @returns FullHealthResponse with detailed status of all services
 */
export async function fetchFullHealth(options?: {
  signal?: AbortSignal;
}): Promise<FullHealthResponse> {
  return fetchApi<FullHealthResponse>('/api/system/health/full', options);
}

/**
 * Fetch GPU statistics.
 *
 * @param options - Optional fetch options including AbortSignal for cancellation (NEM-3411)
 * @returns GPUStats with GPU utilization and memory information
 */
export async function fetchGPUStats(options?: { signal?: AbortSignal }): Promise<GPUStats> {
  return fetchApi<GPUStats>('/api/system/gpu', options);
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

/**
 * Fetch pipeline latency metrics with percentiles.
 * Returns latency statistics for each stage transition in the AI pipeline.
 *
 * @param windowMinutes - Time window for calculating statistics (default: 60)
 * @returns PipelineLatencyResponse with latency stats for each stage
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
 * Fetch pipeline latency history for time-series visualization.
 * Returns latency data grouped into time buckets for charting.
 *
 * @param since - Number of minutes of history to return (1-1440, default: 60)
 * @param bucketSeconds - Size of each time bucket in seconds (10-3600, default: 60)
 * @returns PipelineLatencyHistoryResponse with chronologically ordered snapshots
 */
export async function fetchPipelineLatencyHistory(
  since: number = 60,
  bucketSeconds: number = 60
): Promise<PipelineLatencyHistoryResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('since', String(since));
  queryParams.append('bucket_seconds', String(bucketSeconds));
  return fetchApi<PipelineLatencyHistoryResponse>(
    `/api/system/pipeline-latency/history?${queryParams.toString()}`
  );
}

/**
 * Fetch queue status for all job queues.
 * Returns detailed metrics including depth, workers, throughput, and health status.
 *
 * @returns QueuesStatusResponse with status of all queues and summary
 */
export async function fetchQueuesStatus(): Promise<QueuesStatusResponse> {
  return fetchApi<QueuesStatusResponse>('/api/queues/status');
}

/**
 * Fetch pipeline status including FileWatcher, BatchAggregator, and DegradationManager.
 * Returns real-time visibility into the AI processing pipeline.
 *
 * @returns PipelineStatusResponse with status of all pipeline services
 */
export async function fetchPipelineStatus(): Promise<PipelineStatusResponse> {
  return fetchApi<PipelineStatusResponse>('/api/system/pipeline');
}

/**
 * Fetch WebSocket event type registry (NEM-3639).
 *
 * Returns the complete registry of WebSocket event types including:
 * - Event type identifiers and descriptions
 * - JSON Schema for each event payload
 * - WebSocket channels for subscription
 * - Deprecation information with suggested replacements
 *
 * @returns EventRegistryResponse with all available event types
 */
export async function fetchWebSocketEventTypes(): Promise<EventRegistryResponse> {
  return fetchApi<EventRegistryResponse>('/api/system/websocket/events');
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
    if (params.cursor) {
      // Validate cursor format before sending to API (NEM-2585)
      validateCursorFormat(params.cursor);
      queryParams.append('cursor', params.cursor);
    }
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
  camera_id?: string;
}

/**
 * Fetch event statistics.
 *
 * @param params - Query parameters for filtering events
 * @param options - Optional fetch options including AbortSignal for cancellation (NEM-3411)
 * @returns EventStatsResponse with aggregated statistics
 */
export async function fetchEventStats(
  params?: EventStatsQueryParams,
  options?: { signal?: AbortSignal }
): Promise<GeneratedEventStatsResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/events/stats?${queryString}` : '/api/events/stats';

  return fetchApi<GeneratedEventStatsResponse>(endpoint, options);
}

/**
 * Query parameters for the event clusters endpoint (NEM-3676).
 */
export interface EventClustersQueryParams {
  /** Start date for clustering (ISO format, required) */
  start_date: string;
  /** End date for clustering (ISO format, required) */
  end_date: string;
  /** Filter by camera ID (optional) */
  camera_id?: string;
  /** Time window in minutes for clustering events (1-60, default 5) */
  time_window_minutes?: number;
  /** Minimum events required to form a cluster (2-100, default 2) */
  min_cluster_size?: number;
}

/**
 * Fetch event clusters grouped by temporal proximity (NEM-3676).
 *
 * Groups events that occur within a specified time window into clusters.
 * Events from the same camera within `time_window_minutes` are grouped together.
 * Events from different cameras within 2 minutes are also grouped (cross-camera clusters).
 *
 * @param params - Query parameters for clustering
 * @param options - Optional fetch options including AbortSignal for cancellation
 * @returns EventClustersResponse with clusters and unclustered event count
 */
export async function fetchEventClusters(
  params: EventClustersQueryParams,
  options?: { signal?: AbortSignal }
): Promise<EventClustersResponse> {
  const queryParams = new URLSearchParams();

  // Required parameters
  queryParams.append('start_date', params.start_date);
  queryParams.append('end_date', params.end_date);

  // Optional parameters
  if (params.camera_id) {
    queryParams.append('camera_id', params.camera_id);
  }
  if (params.time_window_minutes !== undefined) {
    queryParams.append('time_window_minutes', String(params.time_window_minutes));
  }
  if (params.min_cluster_size !== undefined) {
    queryParams.append('min_cluster_size', String(params.min_cluster_size));
  }

  const endpoint = `/api/events/clusters?${queryParams.toString()}`;
  return fetchApi<EventClustersResponse>(endpoint, options);
}

export interface EventUpdateData {
  reviewed?: boolean;
  notes?: string | null;
  /** ISO timestamp until which alerts for this event are snoozed (NEM-2359) */
  snooze_until?: string | null;
  /**
   * Optimistic locking version (NEM-3625).
   * Include the version from the event response to detect concurrent modifications.
   * If the version doesn't match on the server, returns HTTP 409 Conflict.
   */
  version?: number;
}

/**
 * Error thrown when an event update fails due to a version conflict (NEM-3625).
 * This occurs when another request modified the event since it was last fetched.
 */
export class EventVersionConflictError extends Error {
  /** The current version of the event on the server */
  public readonly currentVersion: number;
  /** The event ID that had the conflict */
  public readonly eventId: number;

  constructor(eventId: number, currentVersion: number, message?: string) {
    super(
      message ||
        `Event ${eventId} was modified by another request (current version: ${currentVersion}). Please refresh and retry.`
    );
    this.name = 'EventVersionConflictError';
    this.eventId = eventId;
    this.currentVersion = currentVersion;
  }
}

/**
 * Update an event with optimistic locking support (NEM-3625).
 *
 * @param id - Event ID to update
 * @param data - Update data including optional version for optimistic locking
 * @returns Updated event with new version
 * @throws EventVersionConflictError if version mismatch (409 Conflict)
 */
export async function updateEvent(id: number, data: EventUpdateData): Promise<Event> {
  try {
    return await fetchApi<Event>(`/api/events/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  } catch (error) {
    // Handle 409 Conflict for optimistic locking (NEM-3625)
    if (error instanceof ApiError && error.status === 409) {
      // Try to extract the current version and message from the error response
      let currentVersion = 0;
      let message: string | undefined;
      try {
        // Error data contains parsed JSON body: { detail: { message: string, current_version: number } }
        const errorData = error.data as
          | { detail?: { current_version?: number; message?: string } }
          | undefined;
        if (errorData?.detail) {
          if (typeof errorData.detail.current_version === 'number') {
            currentVersion = errorData.detail.current_version;
          }
          if (typeof errorData.detail.message === 'string') {
            message = errorData.detail.message;
          }
        }
      } catch {
        // Ignore parsing errors
      }
      throw new EventVersionConflictError(id, currentVersion, message);
    }
    throw error;
  }
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

/**
 * Snooze an event for a specified duration (NEM-2360).
 *
 * Computes the snooze_until timestamp by adding the specified seconds
 * to the current time and updates the event.
 *
 * @param eventId - ID of the event to snooze
 * @param seconds - Duration in seconds to snooze the event
 * @returns Updated event with snooze_until set
 */
export async function snoozeEvent(eventId: number, seconds: number): Promise<Event> {
  const snoozeUntil = new Date(Date.now() + seconds * 1000).toISOString();
  return updateEvent(eventId, { snooze_until: snoozeUntil });
}

/**
 * Clear the snooze on an event (NEM-2360).
 *
 * Sets snooze_until to null, effectively un-snoozing the event.
 *
 * @param eventId - ID of the event to un-snooze
 * @returns Updated event with snooze_until cleared
 */
export async function clearSnooze(eventId: number): Promise<Event> {
  return updateEvent(eventId, { snooze_until: null });
}

// ============================================================================
// Trash / Soft-Delete Event Endpoints
// ============================================================================

/**
 * Soft-deleted event with deletion timestamp.
 * Used for displaying soft-deleted events in the Trash view.
 */
export interface DeletedEvent extends Event {
  /** Timestamp when the event was soft-deleted */
  deleted_at: string;
}

/**
 * Response from the deleted events endpoint.
 * These events are in the "trash" and can be restored or permanently deleted.
 */
export interface DeletedEventsResponse {
  /** List of soft-deleted events */
  events: DeletedEvent[];
  /** Total count of deleted events (named 'count' in backend, aliased to 'total' for consistency) */
  total: number;
}

/**
 * Backend response type for deleted events with NEM-2075 pagination envelope.
 */
interface DeletedEventsBackendResponse {
  items: DeletedEvent[];
  pagination: {
    total: number;
    limit: number;
    offset?: number | null;
    has_more: boolean;
  };
}

/**
 * Fetch all soft-deleted events for the trash view.
 * Events are ordered by deleted_at descending (most recently deleted first).
 *
 * @param options - Optional fetch options (timeout, abort signal)
 * @returns List of deleted events with total count
 */
export async function fetchDeletedEvents(options?: FetchOptions): Promise<DeletedEventsResponse> {
  const response = await fetchApi<DeletedEventsBackendResponse>('/api/events/deleted', options);
  // Map from NEM-2075 pagination envelope to frontend interface
  return {
    events: response.items,
    total: response.pagination.total,
  };
}

/**
 * Restore a soft-deleted event.
 * This removes the event from trash and makes it visible again in the main event list.
 *
 * @param id - Event ID to restore
 * @returns The restored event
 */
export async function restoreEvent(id: number): Promise<Event> {
  return fetchApi<Event>(`/api/events/${id}/restore`, { method: 'POST' });
}

/**
 * Permanently delete a soft-deleted event.
 * This action cannot be undone - the event and all associated data are permanently removed.
 *
 * @param id - Event ID to permanently delete
 */
export async function permanentlyDeleteEvent(id: number): Promise<void> {
  return fetchApi<void>(`/api/events/${id}`, {
    method: 'DELETE',
    body: JSON.stringify({ soft_delete: false }),
  });
}

// ============================================================================
// Detection Endpoints
// ============================================================================

export async function fetchEventDetections(
  eventId: number,
  params?: DetectionQueryParams
): Promise<GeneratedDetectionListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.cursor) {
      // Validate cursor format before sending to API (NEM-2585)
      validateCursorFormat(params.cursor);
      queryParams.append('cursor', params.cursor);
    }
    // NEM-3629: Support ordering by association timestamp
    if (params.order_detections_by) {
      queryParams.append('order_detections_by', params.order_detections_by);
    }
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/events/${eventId}/detections?${queryString}`
    : `/api/events/${eventId}/detections`;

  return fetchApi<GeneratedDetectionListResponse>(endpoint);
}

/**
 * Fetch enrichment data for all detections in an event with pagination.
 *
 * Returns structured vision model results from the enrichment pipeline for
 * each detection in the event, including:
 * - License plate detection and OCR
 * - Face detection
 * - Vehicle classification
 * - Clothing analysis
 * - Violence detection
 * - Image quality assessment
 * - Pet classification
 *
 * @param eventId - Event ID
 * @param params - Optional pagination parameters (limit, offset)
 * @returns EventEnrichmentsResponse with enrichment data per detection
 *
 * @example
 * ```typescript
 * // Fetch first page of enrichments
 * const enrichments = await fetchEventEnrichments(123);
 *
 * // Fetch with pagination
 * const page2 = await fetchEventEnrichments(123, { limit: 10, offset: 10 });
 * ```
 */
export async function fetchEventEnrichments(
  eventId: number,
  params?: EventEnrichmentsQueryParams
): Promise<GeneratedEventEnrichmentsResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/events/${eventId}/enrichments?${queryString}`
    : `/api/events/${eventId}/enrichments`;

  return fetchApi<GeneratedEventEnrichmentsResponse>(endpoint);
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

export interface DetectionStatsQueryParams {
  camera_id?: string;
}

/**
 * Fetch detection statistics including class distribution.
 *
 * Returns aggregate statistics about detections including counts by object class.
 * Used by the AI Performance page to display detection class distribution charts.
 *
 * @param params Optional query parameters including camera_id filter
 * @returns DetectionStatsResponse with detection statistics
 */
export async function fetchDetectionStats(
  params?: DetectionStatsQueryParams
): Promise<DetectionStatsResponse> {
  const queryParams = new URLSearchParams();

  if (params?.camera_id) {
    queryParams.append('camera_id', params.camera_id);
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/detections/stats?${queryString}` : '/api/detections/stats';

  return fetchApi<DetectionStatsResponse>(endpoint);
}

// ============================================================================
// Detection List, Search, Labels, and Detail Endpoints (NEM-2487)
// ============================================================================

/**
 * Parameters for listing detections with filtering.
 */
export interface DetectionsListParams {
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter by object type (e.g., person, car, truck) */
  object_type?: string;
  /** Filter detections after this date (ISO format) */
  start_date?: string;
  /** Filter detections before this date (ISO format) */
  end_date?: string;
  /** Minimum confidence score (0-1) */
  min_confidence?: number;
  /** Maximum number of results per page */
  limit?: number;
  /** Number of results to skip (deprecated, use cursor) */
  offset?: number;
  /** Cursor for pagination */
  cursor?: string;
}

/**
 * Fetch detections with optional filtering.
 *
 * @param params - Query parameters for filtering and pagination
 * @returns DetectionListResponse with paginated detection results
 */
export async function fetchDetections(
  params?: DetectionsListParams
): Promise<GeneratedDetectionListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
    if (params.object_type) queryParams.append('object_type', params.object_type);
    if (params.start_date) queryParams.append('start_date', params.start_date);
    if (params.end_date) queryParams.append('end_date', params.end_date);
    if (params.min_confidence !== undefined) {
      queryParams.append('min_confidence', String(params.min_confidence));
    }
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.cursor) {
      queryParams.append('cursor', params.cursor);
    }
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/detections?${queryString}` : '/api/detections';

  return fetchApi<GeneratedDetectionListResponse>(endpoint);
}

/**
 * Parameters for searching detections.
 */
export interface DetectionSearchParams {
  /** Search query string */
  query: string;
  /** Filter by labels */
  labels?: string[];
  /** Minimum confidence score (0-1) */
  min_confidence?: number;
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter detections after this date (ISO format) */
  start_date?: string;
  /** Filter detections before this date (ISO format) */
  end_date?: string;
  /** Maximum number of results per page */
  limit?: number;
  /** Number of results to skip */
  offset?: number;
}

/**
 * Search detections with full-text search and filtering.
 *
 * @param params - Search parameters including query and filters
 * @returns DetectionSearchResponse with search results
 */
export async function searchDetections(
  params: DetectionSearchParams
): Promise<GeneratedDetectionSearchResponse> {
  const queryParams = new URLSearchParams();

  queryParams.append('q', params.query);

  if (params.labels && params.labels.length > 0) {
    for (const label of params.labels) {
      queryParams.append('labels', label);
    }
  }
  if (params.min_confidence !== undefined) {
    queryParams.append('min_confidence', String(params.min_confidence));
  }
  if (params.camera_id) queryParams.append('camera_id', params.camera_id);
  if (params.start_date) queryParams.append('start_date', params.start_date);
  if (params.end_date) queryParams.append('end_date', params.end_date);
  if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
  if (params.offset !== undefined) queryParams.append('offset', String(params.offset));

  return fetchApi<GeneratedDetectionSearchResponse>(
    `/api/detections/search?${queryParams.toString()}`
  );
}

/**
 * Fetch available detection labels with counts.
 *
 * @returns DetectionLabelsResponse with labels and their counts
 */
export async function fetchDetectionLabels(): Promise<GeneratedDetectionLabelsResponse> {
  return fetchApi<GeneratedDetectionLabelsResponse>('/api/detections/labels');
}

/**
 * Fetch a single detection by ID.
 *
 * @param detectionId - The detection ID
 * @returns Detection object
 */
export async function fetchDetection(detectionId: number): Promise<GeneratedDetection> {
  return fetchApi<GeneratedDetection>(`/api/detections/${detectionId}`);
}

// ============================================================================
// Detection Bulk Operations (NEM-3649)
// ============================================================================

// Import bulk operation types

// Re-export bulk types for consumers of this module
export type {
  BulkOperationResponse,
  BulkOperationStatus,
  BulkItemResult,
  DetectionBulkCreateItem,
  DetectionBulkCreateResponse,
  DetectionBulkUpdateItem,
} from '../types/bulk';

/**
 * Bulk create detections (up to 100 items per request).
 *
 * Uses HTTP 207 Multi-Status for partial success handling.
 * The response includes per-item results indicating which detections
 * were created successfully and which failed.
 *
 * @param detections - Array of detection items to create (max 100)
 * @returns BulkOperationResponse with per-item results
 * @throws ApiError if the request fails (validation error, server error)
 *
 * @example
 * ```typescript
 * const response = await bulkCreateDetections([
 *   { camera_id: 'cam-1', object_type: 'person', ... },
 *   { camera_id: 'cam-2', object_type: 'vehicle', ... },
 * ]);
 *
 * if (response.succeeded === response.total) {
 *   console.log('All detections created!');
 * } else {
 *   console.log(`${response.failed} detections failed`);
 * }
 * ```
 */
export async function bulkCreateDetections(
  detections: DetectionBulkCreateItem[]
): Promise<DetectionBulkCreateResponse> {
  const response = await fetchApi<DetectionBulkCreateResponse>('/api/detections/bulk', {
    method: 'POST',
    body: JSON.stringify({ detections }),
  });
  return response;
}

/**
 * Bulk update detections (up to 100 items per request).
 *
 * Uses HTTP 207 Multi-Status for partial success handling.
 * Only provided fields will be updated for each detection.
 *
 * @param detections - Array of detection updates with IDs
 * @returns BulkOperationResponse with per-item results
 * @throws ApiError if the request fails (validation error, server error)
 *
 * @example
 * ```typescript
 * const response = await bulkUpdateDetections([
 *   { id: 1, object_type: 'vehicle' }, // Correct misclassification
 *   { id: 2, confidence: 0.99 },
 * ]);
 * ```
 */
export async function bulkUpdateDetections(
  detections: DetectionBulkUpdateItem[]
): Promise<BulkOperationResponse> {
  const response = await fetchApi<BulkOperationResponse>('/api/detections/bulk', {
    method: 'PATCH',
    body: JSON.stringify({ detections }),
  });
  return response;
}

/**
 * Bulk delete detections (up to 100 items per request).
 *
 * Uses HTTP 207 Multi-Status for partial success handling.
 * This is a hard delete - detections cannot be recovered.
 *
 * @param detectionIds - Array of detection IDs to delete (max 100)
 * @returns BulkOperationResponse with per-item results
 * @throws ApiError if the request fails (validation error, server error)
 *
 * @example
 * ```typescript
 * const response = await bulkDeleteDetections([1, 2, 3, 4, 5]);
 *
 * if (response.failed > 0) {
 *   const failed = response.results.filter(r => r.status === 'failed');
 *   console.log('Failed to delete:', failed);
 * }
 * ```
 */
export async function bulkDeleteDetections(detectionIds: number[]): Promise<BulkOperationResponse> {
  const response = await fetchApi<BulkOperationResponse>('/api/detections/bulk', {
    method: 'DELETE',
    body: JSON.stringify({ detection_ids: detectionIds }),
  });
  return response;
}

// ============================================================================
// Analysis Streaming (SSE) Endpoints
// ============================================================================

/**
 * Parameters for the streaming analysis endpoint.
 */
export interface AnalysisStreamParams {
  /** Batch ID to analyze */
  batchId: string;
  /** Camera ID for the batch (optional - uses Redis lookup if not provided) */
  cameraId?: string;
  /** Comma-separated detection IDs (optional) */
  detectionIds?: number[];
}

/**
 * Creates an EventSource connection for streaming LLM analysis progress (NEM-1665).
 *
 * This endpoint provides progressive LLM response updates during long inference
 * times, allowing the frontend to display partial results and show typing
 * indicators while the analysis is in progress.
 *
 * Event Types:
 * - progress: Partial LLM response chunk with accumulated_text
 * - complete: Final event with risk assessment and event_id
 * - error: Error information with error_code and recoverable flag
 *
 * @param params - Analysis stream parameters
 * @returns EventSource object for SSE connection. Caller is responsible for
 *          closing the connection when done.
 *
 * @example
 * ```typescript
 * const eventSource = createAnalysisStream({ batchId: 'batch-123', cameraId: 'cam-1' });
 *
 * eventSource.onmessage = (event) => {
 *   const data = JSON.parse(event.data) as AnalysisStreamEvent;
 *   if (data.event_type === 'progress') {
 *     console.log('Progress:', data.accumulated_text);
 *   } else if (data.event_type === 'complete') {
 *     console.log('Complete:', data.risk_score, data.summary);
 *   } else if (data.event_type === 'error') {
 *     console.error('Error:', data.error_message);
 *   }
 * };
 *
 * eventSource.onerror = (error) => {
 *   console.error('SSE Error:', error);
 *   eventSource.close();
 * };
 *
 * // Clean up when done
 * eventSource.close();
 * ```
 */
export function createAnalysisStream(params: AnalysisStreamParams): EventSource {
  const queryParams = new URLSearchParams();

  if (params.cameraId) {
    queryParams.append('camera_id', params.cameraId);
  }

  if (params.detectionIds && params.detectionIds.length > 0) {
    queryParams.append('detection_ids', params.detectionIds.join(','));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `${BASE_URL}/api/events/analyze/${encodeURIComponent(params.batchId)}/stream?${queryString}`
    : `${BASE_URL}/api/events/analyze/${encodeURIComponent(params.batchId)}/stream`;

  return new EventSource(endpoint);
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
// Frontend Error Logging (NEM-2725)
// ============================================================================

/**
 * Request payload for frontend error logging.
 * Matches the backend FrontendLogCreate schema with error-specific extensions.
 */
export interface FrontendErrorLogRequest {
  /** Log level - always 'ERROR' for error boundaries */
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  /** Human-readable error message */
  message: string;
  /** React component that caught the error */
  component: string;
  /** Current page URL */
  url?: string;
  /** Browser user agent */
  user_agent?: string;
  /** Additional context including stack trace */
  extra?: {
    /** Error stack trace */
    stack?: string;
    /** Source of the error (e.g., 'error_boundary') */
    source?: string;
    /** ISO timestamp */
    timestamp?: string;
    /** React component stack */
    componentStack?: string;
    /** Any additional context */
    [key: string]: unknown;
  };
}

/**
 * Response from the frontend log endpoint.
 */
export interface FrontendErrorLogResponse {
  /** Unique identifier for the log entry */
  id: number;
  /** Status of the log entry */
  status: string;
}

/**
 * Options for creating a frontend error payload.
 */
export interface CreateFrontendErrorPayloadOptions {
  /** Component name that caught the error */
  component?: string;
  /** React component stack trace */
  componentStack?: string;
  /** Source of the error (defaults to 'error_boundary') */
  source?: string;
  /** Additional context to include */
  context?: Record<string, unknown>;
}

/**
 * Log a frontend error to the backend logging endpoint.
 *
 * Use this function when you need to handle logging failures explicitly.
 * For ErrorBoundary usage, prefer `logFrontendErrorNoThrow` which prevents
 * logging failures from causing additional errors.
 *
 * @param payload - The error log payload
 * @returns Promise resolving to the created log entry response
 * @throws ApiError if the request fails
 *
 * @example
 * ```typescript
 * try {
 *   await logFrontendError({
 *     level: 'ERROR',
 *     message: 'Component crashed',
 *     component: 'Dashboard',
 *     extra: { stack: error.stack },
 *   });
 * } catch (e) {
 *   console.error('Failed to log error:', e);
 * }
 * ```
 */
export async function logFrontendError(
  payload: FrontendErrorLogRequest
): Promise<FrontendErrorLogResponse> {
  return fetchApi<FrontendErrorLogResponse>('/api/logs/frontend', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Log a frontend error to the backend without throwing on failure.
 *
 * This is the preferred method for ErrorBoundary components as it ensures
 * that logging failures don't cause additional errors or crash the app.
 * Failures are logged to the console as a warning.
 *
 * @param payload - The error log payload
 * @returns Promise resolving to true if logging succeeded, false otherwise
 *
 * @example
 * ```typescript
 * // In ErrorBoundary.componentDidCatch:
 * const payload = createFrontendErrorPayload(error, { component: 'MyComponent' });
 * await logFrontendErrorNoThrow(payload);
 * // App continues running regardless of logging success
 * ```
 */
export async function logFrontendErrorNoThrow(payload: FrontendErrorLogRequest): Promise<boolean> {
  try {
    await logFrontendError(payload);
    return true;
  } catch (error) {
    // Log to console but don't throw - we don't want logging failures
    // to cause additional errors in the error boundary
    console.warn('Failed to log frontend error to backend:', error);
    return false;
  }
}

/**
 * Create a frontend error log payload from an Error object.
 *
 * Extracts relevant information from the error and constructs a properly
 * formatted payload for the backend logging endpoint.
 *
 * @param error - The error to log
 * @param options - Options for creating the payload
 * @returns FrontendErrorLogRequest ready to send to the backend
 *
 * @example
 * ```typescript
 * // In ErrorBoundary.componentDidCatch:
 * const payload = createFrontendErrorPayload(error, {
 *   component: 'Dashboard',
 *   componentStack: errorInfo.componentStack,
 * });
 * await logFrontendErrorNoThrow(payload);
 * ```
 */
export function createFrontendErrorPayload(
  error: Error,
  options: CreateFrontendErrorPayloadOptions = {}
): FrontendErrorLogRequest {
  const {
    component = extractComponentFromStack(options.componentStack) || 'Unknown',
    componentStack,
    source = 'error_boundary',
    context,
  } = options;

  return {
    level: 'ERROR',
    message: error.message,
    component,
    url: typeof window !== 'undefined' ? window.location.href : undefined,
    user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
    extra: {
      stack: error.stack || undefined,
      source,
      timestamp: new Date().toISOString(),
      ...(componentStack && { componentStack }),
      ...context,
    },
  };
}

/**
 * Extract the component name from a React component stack.
 * Returns the first component name found in the stack, or undefined if not parseable.
 *
 * @internal
 */
function extractComponentFromStack(componentStack?: string): string | undefined {
  if (!componentStack) return undefined;

  // React component stacks look like:
  // "\n    in Dashboard\n    in App"
  // or "\n    at Dashboard\n    at App"
  const match = componentStack.match(/(?:in|at)\s+(\w+)/);
  return match?.[1];
}

/**
 * Get the URL for a detection's thumbnail image (with bounding box).
 * This URL can be used directly in an img src attribute.
 *
 * Note: Detection media endpoints are exempt from API key authentication.
 *
 * @param detectionId - The detection ID
 * @returns The full URL to the detection's thumbnail image endpoint
 */
export function getDetectionImageUrl(detectionId: number): string {
  return `${BASE_URL}/api/detections/${detectionId}/image`;
}

/**
 * Get the URL for a detection's full-size original image (without bounding box).
 * This URL is used by the lightbox viewer to display the full-resolution image.
 *
 * Note: Detection media endpoints are exempt from API key authentication.
 *
 * @param detectionId - The detection ID
 * @returns The full URL to the detection's full-size image endpoint
 */
export function getDetectionFullImageUrl(detectionId: number): string {
  return `${BASE_URL}/api/detections/${detectionId}/image?full=true`;
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

/**
 * Get the URL for a detection's cropped thumbnail image with bounding box overlay.
 *
 * This is an alias for the detection thumbnail endpoint which serves the stored
 * thumbnail or generates one on-the-fly if not available.
 *
 * Note: Detection media endpoints are exempt from API key authentication.
 *
 * @param detectionId - The detection ID
 * @returns The full URL to the detection's thumbnail endpoint
 */
export function getDetectionThumbnailUrl(detectionId: number): string {
  return `${BASE_URL}/api/detections/${detectionId}/thumbnail`;
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

/**
 * Export events as JSON file.
 * Triggers a file download with the exported data.
 *
 * @param params - Optional filter parameters for export
 * @returns Promise that resolves when download is triggered
 */
export async function exportEventsJSON(params?: ExportQueryParams): Promise<void> {
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

  // Build headers with API key and Accept header for JSON format
  const headers: HeadersInit = {
    Accept: 'application/json',
  };
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
    let filename = `events_export_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.json`;
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
// Export Job Endpoints (NEM-2385, NEM-2386)
// ============================================================================

/**
 * Start a new export job with progress tracking.
 * The job runs in the background and can be monitored via getExportStatus.
 *
 * @param params - Export job parameters
 * @returns Promise resolving to the job start response with job_id
 */
export async function startExportJob(
  params: ExportJobCreateParams = {}
): Promise<ExportJobStartResponse> {
  return fetchApi<ExportJobStartResponse>('/api/exports', {
    method: 'POST',
    body: JSON.stringify({
      export_type: params.export_type ?? 'events',
      export_format: params.export_format ?? 'csv',
      camera_id: params.camera_id,
      risk_level: params.risk_level,
      start_date: params.start_date,
      end_date: params.end_date,
      reviewed: params.reviewed,
      columns: params.columns,
    }),
  });
}

/**
 * Get the current status and progress of an export job.
 *
 * @param jobId - The export job ID
 * @returns Promise resolving to the export job status
 */
export async function getExportStatus(jobId: string): Promise<ExportJob> {
  return fetchApi<ExportJob>(`/api/exports/${jobId}`);
}

/**
 * List recent export jobs with optional status filtering.
 *
 * @param status - Optional status filter
 * @param limit - Maximum number of jobs to return (default 50)
 * @param offset - Number of jobs to skip for pagination (default 0)
 * @returns Promise resolving to the paginated list of export jobs
 */
export async function listExportJobs(
  status?: ExportJobStatus,
  limit = 50,
  offset = 0
): Promise<ExportJobListResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('limit', String(limit));
  params.append('offset', String(offset));

  const queryString = params.toString();
  return fetchApi<ExportJobListResponse>(`/api/exports?${queryString}`);
}

/**
 * Cancel a pending or running export job.
 *
 * @param jobId - The export job ID to cancel
 * @returns Promise resolving to the cancellation response
 */
export async function cancelExportJob(jobId: string): Promise<ExportJobCancelResponse> {
  return fetchApi<ExportJobCancelResponse>(`/api/exports/${jobId}`, {
    method: 'DELETE',
  });
}

/**
 * Get download information for a completed export.
 *
 * @param jobId - The export job ID
 * @returns Promise resolving to the download info
 */
export async function getExportDownloadInfo(jobId: string): Promise<ExportDownloadInfo> {
  return fetchApi<ExportDownloadInfo>(`/api/exports/${jobId}/download/info`);
}

/**
 * Download a completed export file.
 * Triggers a file download in the browser.
 *
 * @param jobId - The export job ID
 * @returns Promise that resolves when download is triggered
 */
export async function downloadExportFile(jobId: string): Promise<void> {
  const url = `${BASE_URL}/api/exports/${jobId}/download`;

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
    let filename = `export_${jobId}.csv`;
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
    throw new ApiError(0, error instanceof Error ? error.message : 'Download request failed');
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
  /**
   * Page offset for pagination. Search uses offset-based pagination
   * because it doesn't support cursor pagination on the backend.
   */
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
// Event Feedback Endpoints
// ============================================================================

/**
 * Submit feedback for an event.
 *
 * Allows users to mark events as correct, false positive, wrong severity,
 * or missed detection. This feedback is used to improve AI model performance.
 *
 * @param feedback - The feedback data including event_id, feedback_type, and optional notes
 * @returns EventFeedbackResponse with the created feedback record
 * @throws ApiError with 404 if event not found, 409 if feedback already exists
 */
export async function submitEventFeedback(
  feedback: EventFeedbackCreate
): Promise<EventFeedbackResponse> {
  return fetchApi<EventFeedbackResponse>('/api/feedback', {
    method: 'POST',
    body: JSON.stringify(feedback),
  });
}

/**
 * Get existing feedback for an event.
 *
 * Retrieves any previously submitted feedback for the specified event.
 * Returns null if no feedback exists (404 response is handled as null).
 *
 * @param eventId - The event ID to get feedback for
 * @returns EventFeedbackResponse if feedback exists, null if not found
 */
export async function getEventFeedback(eventId: number): Promise<EventFeedbackResponse | null> {
  try {
    return await fetchApi<EventFeedbackResponse>(`/api/feedback/event/${eventId}`);
  } catch (error) {
    // Return null for 404 (no feedback found) - this is expected behavior
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
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

/**
 * Fetch cleanup service status.
 *
 * @returns CleanupStatusResponse with cleanup service status
 */
export async function fetchCleanupStatus(): Promise<CleanupStatusResponse> {
  return fetchApi<CleanupStatusResponse>('/api/system/cleanup/status');
}

/**
 * Preview orphaned files that would be cleaned up.
 * Orphaned files are files on disk not referenced in the database.
 *
 * @returns OrphanedFileCleanupResponse with list and count of orphaned files
 */
export async function previewOrphanedFiles(): Promise<OrphanedFileCleanupResponse> {
  return fetchApi<OrphanedFileCleanupResponse>('/api/system/cleanup/orphaned-files?dry_run=true', {
    method: 'POST',
  });
}

/**
 * Trigger orphaned file cleanup to delete files on disk not referenced in database.
 *
 * @returns OrphanedFileCleanupResponse with statistics about deleted files
 */
export async function triggerOrphanedCleanup(): Promise<OrphanedFileCleanupResponse> {
  return fetchApi<OrphanedFileCleanupResponse>('/api/system/cleanup/orphaned-files?dry_run=false', {
    method: 'POST',
  });
}

// ============================================================================
// Job Endpoints
// ============================================================================

/**
 * Query parameters for job list endpoint.
 */
export interface JobsQueryParams {
  /** Filter by job type (e.g., 'export', 'cleanup') */
  job_type?: string;
  /** Filter by job status */
  status?: JobStatusEnum;
}

/**
 * Fetch list of background jobs with optional filtering.
 *
 * @param params - Optional query parameters for filtering jobs
 * @returns JobListResponse with list of jobs
 */
export async function fetchJobs(params?: JobsQueryParams): Promise<JobListResponse> {
  const queryParams = new URLSearchParams();
  if (params?.job_type) queryParams.append('job_type', params.job_type);
  if (params?.status) queryParams.append('status', params.status);

  const queryString = queryParams.toString();
  const url = queryString ? `/api/jobs?${queryString}` : '/api/jobs';
  return fetchApi<JobListResponse>(url);
}

/**
 * Fetch a specific job by ID.
 *
 * @param jobId - The job ID to fetch
 * @returns JobResponse with job details
 */
export async function fetchJob(jobId: string): Promise<JobResponse> {
  return fetchApi<JobResponse>(`/api/jobs/${jobId}`);
}

/**
 * Query parameters for fetching job logs.
 */
export interface JobLogsQueryParams {
  /** Maximum number of logs to return (default 100) */
  limit?: number;
  /** Number of logs to skip (default 0) */
  offset?: number;
  /** Filter by log level (DEBUG, INFO, WARN, ERROR) */
  level?: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
}

/**
 * Fetch logs for a specific job by ID.
 *
 * @param jobId - The job ID to fetch logs for
 * @param params - Optional query parameters for filtering logs
 * @returns JobLogsResponse with log entries
 */
export async function fetchJobLogs(
  jobId: string,
  params?: JobLogsQueryParams
): Promise<JobLogsResponse> {
  const queryParams = new URLSearchParams();
  if (params?.limit !== undefined) queryParams.append('limit', String(params.limit));
  if (params?.offset !== undefined) queryParams.append('offset', String(params.offset));
  if (params?.level) queryParams.append('level', params.level);

  const queryString = queryParams.toString();
  const url = queryString ? `/api/jobs/${jobId}/logs?${queryString}` : `/api/jobs/${jobId}/logs`;
  return fetchApi<JobLogsResponse>(url);
}

/**
 * Fetch detailed job information by ID.
 *
 * @param jobId - The job ID to fetch
 * @returns JobDetailResponse with full job details including retry info and timing
 */
export async function fetchJobDetail(jobId: string): Promise<JobDetailResponse> {
  return fetchApi<JobDetailResponse>(`/api/jobs/${jobId}/detail`);
}

/**
 * Fetch job history including state transitions.
 *
 * @param jobId - The job ID to fetch history for
 * @returns JobHistoryResponse with transitions and attempts
 */
export async function fetchJobHistory(jobId: string): Promise<JobHistoryResponse> {
  return fetchApi<JobHistoryResponse>(`/api/jobs/${jobId}/history`);
}

/**
 * Query parameters for job search endpoint.
 */
export interface JobsSearchQueryParams {
  /** Search query text */
  q?: string;
  /** Filter by job status */
  status?: JobStatusEnum;
  /** Filter by job type (e.g., 'export', 'batch_audit', 'cleanup', 're_evaluation') */
  type?: string;
  /** Maximum number of jobs to return (default 50) */
  limit?: number;
  /** Number of jobs to skip (default 0) */
  offset?: number;
}

/**
 * Search jobs with optional filters.
 *
 * This endpoint provides advanced search functionality with aggregations
 * for faceted filtering. Supports text search across job fields, status
 * filtering, and type filtering.
 *
 * @param params - Search query parameters
 * @returns JobSearchResponse with jobs, pagination meta, and aggregations
 */
export async function searchJobs(params?: JobsSearchQueryParams): Promise<JobSearchResponse> {
  const queryParams = new URLSearchParams();
  if (params?.q) queryParams.append('q', params.q);
  if (params?.status) queryParams.append('status', params.status);
  if (params?.type) queryParams.append('type', params.type);
  if (params?.limit !== undefined) queryParams.append('limit', String(params.limit));
  if (params?.offset !== undefined) queryParams.append('offset', String(params.offset));

  const queryString = queryParams.toString();
  const url = queryString ? `/api/jobs/search?${queryString}` : '/api/jobs/search';
  return fetchApi<JobSearchResponse>(url);
}

/**
 * Cancel a job (graceful cancellation).
 *
 * Requests graceful cancellation of a pending or running job.
 * Jobs that are already completed or failed cannot be cancelled.
 *
 * @param jobId - The job ID to cancel
 * @returns JobCancelResponse with cancellation status
 */
export async function cancelJob(jobId: string): Promise<JobCancelResponse> {
  return fetchApi<JobCancelResponse>(`/api/jobs/${jobId}/cancel`, {
    method: 'POST',
  });
}

/**
 * Abort a running job (force stop).
 *
 * Forces immediate termination of a running job by sending abort signal
 * to the worker. Only jobs with status 'running' can be aborted.
 * For queued jobs, use cancelJob instead.
 *
 * WARNING: Force abort may cause data inconsistency. Use with caution.
 *
 * @param jobId - The job ID to abort
 * @returns JobAbortResponse with abort status
 */
export async function abortJob(jobId: string): Promise<JobAbortResponse> {
  return fetchApi<JobAbortResponse>(`/api/jobs/${jobId}/abort`, {
    method: 'POST',
  });
}

/**
 * Retry a failed or cancelled job.
 *
 * Creates a new job with the same parameters as the original failed job.
 * Only jobs with status 'failed' or 'cancelled' can be retried.
 *
 * @param jobId - The job ID to retry
 * @returns JobResponse with the new job details
 */
export async function retryJob(jobId: string): Promise<JobResponse> {
  return fetchApi<JobResponse>(`/api/jobs/${jobId}/retry`, {
    method: 'POST',
  });
}

/**
 * Delete a job record.
 *
 * Permanently removes a job record from the database.
 * Jobs that are currently running cannot be deleted - cancel or abort first.
 *
 * @param jobId - The job ID to delete
 * @returns JobCancelResponse with deletion status
 */
export async function deleteJob(jobId: string): Promise<JobCancelResponse> {
  return fetchApi<JobCancelResponse>(`/api/jobs/${jobId}`, {
    method: 'DELETE',
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

  if (recipients?.length) {
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

/**
 * Notification configuration update request
 */
export interface NotificationConfigUpdate {
  smtp_enabled?: boolean;
  smtp_host?: string | null;
  smtp_port?: number | null;
  smtp_from_address?: string | null;
  webhook_enabled?: boolean;
  default_webhook_url?: string | null;
}

/**
 * Notification configuration update response
 */
export interface NotificationConfigUpdateResponse {
  smtp_enabled: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_from_address: string | null;
  webhook_enabled: boolean;
  default_webhook_url: string | null;
  message: string;
}

/**
 * Update notification configuration.
 *
 * @param update - Partial configuration update with fields to change
 * @returns NotificationConfigUpdateResponse with updated configuration
 */
export async function updateNotificationConfig(
  update: NotificationConfigUpdate
): Promise<NotificationConfigUpdateResponse> {
  return fetchApi<NotificationConfigUpdateResponse>('/api/notification/config', {
    method: 'PATCH',
    body: JSON.stringify(update),
  });
}

/**
 * Query parameters for fetching notification history
 */
export interface NotificationHistoryQueryParams {
  /** Filter by alert ID */
  alert_id?: string;
  /** Filter by notification channel */
  channel?: NotificationChannel;
  /** Filter by success status */
  success?: boolean;
  /** Maximum number of results to return (1-100, default 50) */
  limit?: number;
  /** Number of results to skip for pagination (default 0) */
  offset?: number;
}

/**
 * A notification delivery history entry
 */
export interface NotificationHistoryEntry {
  /** Notification delivery ID */
  id: string;
  /** Associated alert ID */
  alert_id: string;
  /** Notification channel */
  channel: NotificationChannel;
  /** Recipient identifier */
  recipient?: string | null;
  /** Whether delivery was successful */
  success: boolean;
  /** Error message if failed */
  error?: string | null;
  /** Delivery timestamp */
  delivered_at?: string | null;
  /** Record creation timestamp */
  created_at: string;
}

/**
 * Response for notification history list
 */
export interface NotificationHistoryResponse {
  /** Total number of entries matching filters */
  count: number;
  /** Notification history entries */
  entries: NotificationHistoryEntry[];
  /** Maximum number of results returned */
  limit: number;
  /** Number of results skipped */
  offset: number;
}

/**
 * Fetch notification delivery history with optional filters.
 *
 * @param params - Query parameters for filtering and pagination
 * @returns NotificationHistoryResponse with delivery history entries
 */
export async function fetchNotificationHistory(
  params?: NotificationHistoryQueryParams
): Promise<NotificationHistoryResponse> {
  const searchParams = new URLSearchParams();

  if (params?.alert_id) {
    searchParams.set('alert_id', params.alert_id);
  }
  if (params?.channel) {
    searchParams.set('channel', params.channel);
  }
  if (params?.success !== undefined) {
    searchParams.set('success', String(params.success));
  }
  if (params?.limit !== undefined) {
    searchParams.set('limit', String(params.limit));
  }
  if (params?.offset !== undefined) {
    searchParams.set('offset', String(params.offset));
  }

  const queryString = searchParams.toString();
  const url = queryString ? `/api/notification/history?${queryString}` : '/api/notification/history';

  return fetchApi<NotificationHistoryResponse>(url);
}

// ============================================================================
// Notification Preferences Endpoints
// ============================================================================

/**
 * Fetch global notification preferences.
 *
 * @returns NotificationPreferencesResponse with current global preferences
 */
export async function fetchNotificationPreferences(): Promise<NotificationPreferencesResponse> {
  return fetchApi<NotificationPreferencesResponse>('/api/notification-preferences/');
}

/**
 * Update global notification preferences.
 *
 * @param update - Partial update with fields to change
 * @returns NotificationPreferencesResponse with updated preferences
 */
export async function updateNotificationPreferences(
  update: NotificationPreferencesUpdate
): Promise<NotificationPreferencesResponse> {
  return fetchApi<NotificationPreferencesResponse>('/api/notification-preferences/', {
    method: 'PUT',
    body: JSON.stringify(update),
  });
}

/**
 * Fetch all camera notification settings.
 *
 * @returns CameraNotificationSettingsListResponse with all camera settings
 */
export async function fetchCameraNotificationSettings(): Promise<CameraNotificationSettingsListResponse> {
  return fetchApi<CameraNotificationSettingsListResponse>('/api/notification-preferences/cameras');
}

/**
 * Fetch notification setting for a specific camera.
 *
 * @param cameraId - Camera ID
 * @returns CameraNotificationSettingResponse for the camera
 */
export async function fetchCameraNotificationSetting(
  cameraId: string
): Promise<CameraNotificationSettingResponse> {
  return fetchApi<CameraNotificationSettingResponse>(
    `/api/notification-preferences/cameras/${encodeURIComponent(cameraId)}`
  );
}

/**
 * Update notification setting for a specific camera.
 *
 * @param cameraId - Camera ID
 * @param update - Partial update with fields to change
 * @returns CameraNotificationSettingResponse with updated setting
 */
export async function updateCameraNotificationSetting(
  cameraId: string,
  update: CameraNotificationSettingUpdate
): Promise<CameraNotificationSettingResponse> {
  return fetchApi<CameraNotificationSettingResponse>(
    `/api/notification-preferences/cameras/${encodeURIComponent(cameraId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(update),
    }
  );
}

/**
 * Fetch all quiet hours periods.
 *
 * @returns QuietHoursPeriodsListResponse with all quiet periods
 */
export async function fetchQuietHoursPeriods(): Promise<QuietHoursPeriodsListResponse> {
  return fetchApi<QuietHoursPeriodsListResponse>('/api/notification-preferences/quiet-hours');
}

/**
 * Create a new quiet hours period.
 *
 * @param period - Quiet hours period to create
 * @returns QuietHoursPeriodResponse with created period
 */
export async function createQuietHoursPeriod(
  period: QuietHoursPeriodCreate
): Promise<QuietHoursPeriodResponse> {
  return fetchApi<QuietHoursPeriodResponse>('/api/notification-preferences/quiet-hours', {
    method: 'POST',
    body: JSON.stringify(period),
  });
}

/**
 * Delete a quiet hours period.
 *
 * @param periodId - Period UUID to delete
 */
export async function deleteQuietHoursPeriod(periodId: string): Promise<void> {
  await fetchApi<void>(
    `/api/notification-preferences/quiet-hours/${encodeURIComponent(periodId)}`,
    {
      method: 'DELETE',
    }
  );
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
  /**
   * Page offset for pagination. Use cursor instead for better performance with large datasets.
   * @deprecated Prefer cursor-based pagination for new code.
   */
  offset?: number;
  /**
   * Cursor for pagination. Pass the `next_cursor` value from the previous response.
   * Recommended over offset pagination for better performance.
   */
  cursor?: string;
  /**
   * Include total count in response. Defaults to false for performance.
   * Set to true when displaying "X of Y results" in UI.
   */
  include_total_count?: boolean;
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
    // Prefer cursor over offset for pagination
    if (params.cursor) {
      queryParams.append('cursor', params.cursor);
    } else if (params.offset !== undefined) {
      queryParams.append('offset', String(params.offset));
    }
    // Include total count when requested (needed for "X of Y results" display)
    if (params.include_total_count) {
      queryParams.append('include_total_count', 'true');
    }
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
  /**
   * Cursor for pagination. Pass the `next_cursor` value from the previous response.
   */
  cursor?: string;
}

/**
 * Fetch all alert rules with optional filtering and pagination.
 *
 * @param params - Query parameters for filtering
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
    if (params.cursor) {
      queryParams.append('cursor', params.cursor);
    }
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/alerts/rules?${queryString}` : '/api/alerts/rules';

  return fetchApi<AlertRuleListResponse>(endpoint);
}

/**
 * Fetch a single alert rule by ID.
 *
 * @param id - Alert rule UUID
 * @returns AlertRule with rule details
 */
export async function fetchAlertRule(id: string): Promise<AlertRule> {
  return fetchApi<AlertRule>(`/api/alerts/rules/${id}`);
}

/**
 * Create a new alert rule.
 *
 * @param data - Alert rule creation data
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
 * @param id - Alert rule UUID
 * @param data - Alert rule update data
 * @returns Updated AlertRule
 */
export async function updateAlertRule(id: string, data: AlertRuleUpdate): Promise<AlertRule> {
  return fetchApi<AlertRule>(`/api/alerts/rules/${id}`, {
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
export async function testAlertRule(
  id: string,
  request?: RuleTestRequest
): Promise<RuleTestResponse> {
  return fetchApi<RuleTestResponse>(`/api/alerts/rules/${id}/test`, {
    method: 'POST',
    body: JSON.stringify(request || { limit: 10 }),
  });
}

// ============================================================================
// Alert Instance Endpoints
// ============================================================================

/**
 * Acknowledge an alert.
 *
 * Marks the alert as acknowledged and broadcasts the state change via WebSocket.
 * Only alerts with status PENDING or DELIVERED can be acknowledged.
 *
 * @param alertId - Alert UUID
 * @returns Updated AlertResponse with status 'acknowledged'
 * @throws ApiError with status 404 if alert not found
 * @throws ApiError with status 409 if alert cannot be acknowledged (wrong status or concurrent modification)
 */
export async function acknowledgeAlert(alertId: string): Promise<AlertResponse> {
  return fetchApi<AlertResponse>(`/api/alerts/${alertId}/acknowledge`, {
    method: 'POST',
  });
}

/**
 * Dismiss an alert.
 *
 * Marks the alert as dismissed and broadcasts the state change via WebSocket.
 * Only alerts with status PENDING, DELIVERED, or ACKNOWLEDGED can be dismissed.
 *
 * @param alertId - Alert UUID
 * @returns Updated AlertResponse with status 'dismissed'
 * @throws ApiError with status 404 if alert not found
 * @throws ApiError with status 409 if alert cannot be dismissed (wrong status or concurrent modification)
 */
export async function dismissAlert(alertId: string): Promise<AlertResponse> {
  return fetchApi<AlertResponse>(`/api/alerts/${alertId}/dismiss`, {
    method: 'POST',
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
export async function resetCircuitBreaker(
  name: string
): Promise<GeneratedCircuitBreakerResetResponse> {
  return fetchApi<GeneratedCircuitBreakerResetResponse>(
    `/api/system/circuit-breakers/${encodeURIComponent(name)}/reset`,
    { method: 'POST' }
  );
}

// ============================================================================
// Service Management Endpoints
// ============================================================================

/**
 * Service information from the container orchestrator
 */
export interface ServiceInfo {
  name: string;
  display_name: string;
  category: 'infrastructure' | 'ai' | 'monitoring';
  status: string;
  enabled: boolean;
  container_id?: string | null;
  image?: string | null;
  port: number;
  failure_count: number;
  restart_count: number;
  last_restart_at?: string | null;
  uptime_seconds?: number | null;
}

/**
 * Response from service action endpoints (restart, start, stop, enable, disable)
 */
export interface ServiceActionResponse {
  success: boolean;
  message: string;
  service: ServiceInfo;
}

/**
 * @deprecated Use ServiceActionResponse instead
 * Legacy response type kept for backward compatibility
 */
export interface ServiceRestartResponse {
  service: string;
  status: 'restarting' | 'restart_failed' | 'already_restarting';
  message: string;
  timestamp: string;
}

/**
 * Restart a specific service.
 *
 * Triggers a restart of the named service (e.g., rtdetr, nemotron).
 * The restart is asynchronous - the service will go through a restart cycle
 * and its status will be broadcast via WebSocket when complete.
 *
 * @param name - The name of the service to restart (e.g., 'rtdetr', 'nemotron')
 * @returns ServiceActionResponse with restart confirmation
 * @throws ApiError 400 if service is disabled
 * @throws ApiError 404 if service not found
 * @throws ApiError 503 if orchestrator not available
 */
export async function restartService(name: string): Promise<ServiceActionResponse> {
  return fetchApi<ServiceActionResponse>(
    `/api/system/services/${encodeURIComponent(name)}/restart`,
    { method: 'POST' }
  );
}

/**
 * Start a stopped service.
 *
 * Starts a service that was previously stopped. Will fail if the service
 * is already running or is disabled (must be enabled first).
 *
 * @param name - The name of the service to start (e.g., 'rtdetr', 'nemotron')
 * @returns ServiceActionResponse with start confirmation
 * @throws ApiError 400 if service is already running or disabled
 * @throws ApiError 404 if service not found
 * @throws ApiError 503 if orchestrator not available
 */
export async function startService(name: string): Promise<ServiceActionResponse> {
  return fetchApi<ServiceActionResponse>(`/api/system/services/${encodeURIComponent(name)}/start`, {
    method: 'POST',
  });
}

/**
 * Stop/disable a running service.
 *
 * Disables a service, stopping it and preventing auto-restart.
 * Use enableService to re-enable and restart the service.
 *
 * Note: This maps to the backend's disable endpoint as there is no
 * explicit stop endpoint. Disabling stops the service and prevents
 * self-healing restarts.
 *
 * @param name - The name of the service to stop (e.g., 'rtdetr', 'nemotron')
 * @returns ServiceActionResponse with disable confirmation
 * @throws ApiError 404 if service not found
 * @throws ApiError 503 if orchestrator not available
 */
export async function stopService(name: string): Promise<ServiceActionResponse> {
  return fetchApi<ServiceActionResponse>(
    `/api/system/services/${encodeURIComponent(name)}/disable`,
    { method: 'POST' }
  );
}

/**
 * Enable a disabled service.
 *
 * Re-enables a service that was previously disabled. The orchestrator
 * will start the service if it's not already running.
 *
 * @param name - The name of the service to enable (e.g., 'rtdetr', 'nemotron')
 * @returns ServiceActionResponse with enable confirmation
 * @throws ApiError 404 if service not found
 * @throws ApiError 503 if orchestrator not available
 */
export async function enableService(name: string): Promise<ServiceActionResponse> {
  return fetchApi<ServiceActionResponse>(
    `/api/system/services/${encodeURIComponent(name)}/enable`,
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
  return fetchApi<EnrichmentResponse>(`/api/detections/${detectionId}/enrichment`);
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
  return fetchApi<AllPromptsResponse>('/api/prompts');
}

/**
 * Fetch current prompt configuration for a specific AI model.
 *
 * @param model - Model name (nemotron, florence2, yolo_world, xclip, fashion_clip)
 * @returns ModelPromptResponse with current configuration
 */
export async function fetchModelPrompt(model: PromptModelName): Promise<ModelPromptResponse> {
  return fetchApi<ModelPromptResponse>(`/api/prompts/${model}`);
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
  return fetchApi<PromptUpdateResponse>(`/api/prompts/${model}`, {
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
  return fetchApi<PromptTestResponse>('/api/prompts/test', {
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
    `/api/prompts/history?${queryParams.toString()}`
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
  return fetchApi<PromptHistoryResponse>(`/api/prompts/history/${model}?${queryParams.toString()}`);
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
  return fetchApi<PromptRestoreResponse>(`/api/prompts/history/${version}?model=${model}`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Export all AI model configurations as JSON.
 *
 * @returns PromptExportResponse with all configurations
 */
export async function exportPrompts(): Promise<PromptExportResponse> {
  return fetchApi<PromptExportResponse>('/api/prompts/export');
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
  return fetchApi<PromptImportResponse>('/api/prompts/import', {
    method: 'POST',
    body: JSON.stringify({ prompts, overwrite }),
  });
}

// ============================================================================
// Entity Re-Identification Endpoints
// ============================================================================

// Entity types are re-exported from generated types:
// EntityAppearance, EntitySummary, EntityDetail, EntityListResponse, EntityHistoryResponse

/**
 * Entity match result from re-identification.
 * Represents a match between a detected entity in an event and a known entity.
 */
export interface EntityMatch {
  /** Unique entity identifier */
  entity_id: string;
  /** Type of entity ('person' or 'vehicle') */
  entity_type: 'person' | 'vehicle';
  /** Similarity score between matched embeddings (0-1) */
  similarity: number;
  /** Time gap in seconds since this entity was last seen */
  time_gap_seconds: number;
  /** Camera where entity was last seen */
  last_seen_camera: string;
  /** Timestamp when entity was last seen */
  last_seen_at: string;
  /** Thumbnail URL of the entity */
  thumbnail_url: string | null;
  /** Additional attributes (clothing, carrying items, vehicle type, etc.) */
  attributes?: Record<string, unknown>;
}

/**
 * Response containing entity matches for an event.
 */
export interface EventEntityMatchesResponse {
  /** Event ID */
  event_id: number;
  /** Person entity matches */
  person_matches: EntityMatch[];
  /** Vehicle entity matches */
  vehicle_matches: EntityMatch[];
  /** Total number of matches */
  total_matches: number;
}

/**
 * Query parameters for fetching entities
 */
export interface EntitiesQueryParams {
  /** Filter by entity type ('person' or 'vehicle') */
  entity_type?: 'person' | 'vehicle';
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter entities seen since this timestamp (ISO format) */
  since?: string;
  /** Maximum number of results (1-1000, default 50) */
  limit?: number;
  /**
   * Cursor for pagination. Pass the `next_cursor` value from the previous response.
   */
  cursor?: string;
}

/**
 * Fetch tracked entities with optional filtering and pagination.
 *
 * Returns a paginated list of entities that have been tracked via
 * re-identification (persons and vehicles seen across cameras).
 *
 * @param params - Query parameters for filtering
 * @param options - Fetch options including AbortSignal
 * @returns EntityListResponse with filtered entities and pagination info
 */
export async function fetchEntities(
  params?: EntitiesQueryParams,
  options?: FetchOptions
): Promise<EntityListResponse> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.entity_type) queryParams.append('entity_type', params.entity_type);
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
    if (params.since) queryParams.append('since', params.since);
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.cursor) {
      queryParams.append('cursor', params.cursor);
    }
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/entities?${queryString}` : '/api/entities';

  return fetchApi<EntityListResponse>(endpoint, options);
}

/**
 * Fetch detailed information about a specific entity.
 *
 * Returns the entity's summary information along with all recorded appearances.
 *
 * @param entityId - Unique entity identifier
 * @returns EntityDetail with full entity information including appearances
 */
export async function fetchEntity(entityId: string): Promise<EntityDetail> {
  return fetchApi<EntityDetail>(`/api/entities/${encodeURIComponent(entityId)}`);
}

/**
 * Fetch the appearance timeline for a specific entity.
 *
 * Returns a chronological list of all appearances for the entity
 * across all cameras.
 *
 * @param entityId - Unique entity identifier
 * @returns EntityHistoryResponse with appearance timeline
 */
export async function fetchEntityHistory(entityId: string): Promise<EntityHistoryResponse> {
  return fetchApi<EntityHistoryResponse>(`/api/entities/${encodeURIComponent(entityId)}/history`);
}

/**
 * Single entity match result from re-identification
 */
export interface EntityMatchItem {
  entity_id: string;
  entity_type: 'person' | 'vehicle';
  camera_id: string;
  camera_name: string | null;
  timestamp: string;
  thumbnail_url: string | null;
  similarity_score: number;
  time_gap_seconds: number;
  attributes: Record<string, unknown>;
}

/**
 * Response from entity match query
 */
export interface EntityMatchResponse {
  query_detection_id: string;
  entity_type: string;
  matches: EntityMatchItem[];
  total_matches: number;
  threshold: number;
}

/**
 * Query parameters for fetching entity matches
 */
export interface EntityMatchQueryParams {
  /** Type of entity to search ('person' or 'vehicle') */
  entity_type?: 'person' | 'vehicle';
  /** Minimum similarity threshold (0-1, default 0.85) */
  threshold?: number;
}

/**
 * Fetch entities matching a specific detection's embedding.
 *
 * Searches for entities similar to the specified detection across all cameras.
 * Used to show re-ID matches in the EventDetailModal.
 *
 * Returns null if no embedding exists for the detection (404 response),
 * which is expected behavior for detections without re-ID embeddings.
 *
 * @param detectionId - Detection ID to find matches for
 * @param params - Query parameters for filtering
 * @param options - Fetch options including AbortSignal
 * @returns EntityMatchResponse with matching entities, or null if no embedding exists
 */
export async function fetchEntityMatches(
  detectionId: string,
  params?: EntityMatchQueryParams,
  options?: FetchOptions
): Promise<EntityMatchResponse | null> {
  const queryParams = new URLSearchParams();

  if (params) {
    if (params.entity_type) queryParams.append('entity_type', params.entity_type);
    if (params.threshold !== undefined) queryParams.append('threshold', String(params.threshold));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/api/entities/matches/${encodeURIComponent(detectionId)}?${queryString}`
    : `/api/entities/matches/${encodeURIComponent(detectionId)}`;

  try {
    return await fetchApi<EntityMatchResponse>(endpoint, options);
  } catch (error) {
    // Return null for 404 (no embedding exists) - this is expected behavior
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

/**
 * Fetch entity re-ID matches for a specific event.
 *
 * Returns any entities (persons or vehicles) that were matched via
 * re-identification for this event, including similarity scores.
 *
 * Note: This endpoint may return 404 if no matches exist for the event,
 * which is handled gracefully by returning empty arrays.
 *
 * @param eventId - Numeric event ID
 * @returns EventEntityMatchesResponse with matched entities
 */
export async function fetchEventEntityMatches(
  eventId: number
): Promise<EventEntityMatchesResponse> {
  try {
    return await fetchApi<EventEntityMatchesResponse>(`/api/events/${eventId}/entity-matches`);
  } catch (error) {
    // If no matches exist (404) or endpoint not implemented, return empty response
    if (error instanceof ApiError && (error.status === 404 || error.status === 501)) {
      return {
        event_id: eventId,
        person_matches: [],
        vehicle_matches: [],
        total_matches: 0,
      };
    }
    throw error;
  }
}

// ============================================================================
// Enriched Suggestion Types (Prompt Playground)
// ============================================================================

/**
 * Example of how a suggestion could improve a specific event's analysis.
 *
 * Shows the potential impact of applying a suggestion by comparing
 * before/after risk scores for a real event.
 */
export interface ExampleImprovement {
  /** The event ID used as an example */
  eventId: number;
  /** Risk score with original prompt (0-100) */
  beforeScore: number;
  /** Estimated risk score if suggestion is applied (0-100) */
  estimatedAfterScore: number;
}

/**
 * Enhanced suggestion schema for smart prompt modification.
 *
 * Extends the basic recommendation with fields for:
 * - Smart application: Identifies where and how to insert the suggestion
 * - Learning mode: Explains impact with evidence from actual events
 *
 * Used by the Prompt Playground to transform AI audit recommendations
 * into actionable prompt improvements through a progressive disclosure UX.
 */
export interface EnrichedSuggestion {
  /**
   * Suggestion category.
   * - missing_context: Context that should be added to the prompt
   * - unused_data: Data in the prompt that is not being utilized
   * - model_gaps: Missing model integrations or capabilities
   * - format_suggestions: Structural or formatting improvements
   */
  category: 'missing_context' | 'unused_data' | 'model_gaps' | 'format_suggestions';

  /** The improvement suggestion text */
  suggestion: string;

  /** Priority level for this suggestion */
  priority: 'high' | 'medium' | 'low';

  /** How many events mentioned this suggestion */
  frequency: number;

  /** Target section header in the prompt (e.g., 'Camera & Time Context') */
  targetSection: string;

  /** Where to insert the suggestion: append, prepend, or replace */
  insertionPoint: 'append' | 'prepend' | 'replace';

  /** The variable to add (e.g., '{time_since_last_event}') */
  proposedVariable: string;

  /** Human-readable label for the variable (e.g., 'Time Since Last Event:') */
  proposedLabel: string;

  /** Explanation of why this suggestion matters and its expected impact */
  impactExplanation: string;

  /** IDs of events that triggered this suggestion */
  sourceEventIds: number[];

  /** Optional example showing before/after scores for a specific event */
  exampleImprovement?: ExampleImprovement;
}

// ============================================================================
// Scene Change Detection Endpoints
// ============================================================================

/**
 * Fetch scene changes for a camera with pagination.
 *
 * Returns detected camera view changes that may indicate tampering, angle changes,
 * or blocked views. Uses cursor-based pagination for efficient navigation.
 *
 * @param cameraId - Camera ID to fetch scene changes for
 * @param options - Optional query parameters
 * @param options.acknowledged - Filter by acknowledgement status
 * @param options.limit - Maximum number of results (default: 50)
 * @param options.cursor - Cursor for pagination (ISO 8601 timestamp)
 * @returns SceneChangeListResponse with list of scene changes and pagination info
 * @throws ApiError 404 if camera not found
 */
export async function fetchSceneChanges(
  cameraId: string,
  options?: {
    acknowledged?: boolean;
    limit?: number;
    cursor?: string;
  }
): Promise<SceneChangeListResponse> {
  const params = new URLSearchParams();
  if (options?.acknowledged !== undefined) {
    params.append('acknowledged', String(options.acknowledged));
  }
  if (options?.limit !== undefined) {
    params.append('limit', String(options.limit));
  }
  if (options?.cursor) {
    params.append('cursor', options.cursor);
  }

  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchApi<SceneChangeListResponse>(
    `/api/cameras/${encodeURIComponent(cameraId)}/scene-changes${query}`
  );
}

/**
 * Acknowledge a scene change alert.
 *
 * Marks a scene change as acknowledged to indicate it has been reviewed.
 *
 * @param cameraId - Camera ID
 * @param sceneChangeId - Scene change ID to acknowledge
 * @returns SceneChangeAcknowledgeResponse confirming acknowledgement
 * @throws ApiError 404 if camera or scene change not found
 */
export async function acknowledgeSceneChange(
  cameraId: string,
  sceneChangeId: number
): Promise<SceneChangeAcknowledgeResponse> {
  return fetchApi<SceneChangeAcknowledgeResponse>(
    `/api/cameras/${encodeURIComponent(cameraId)}/scene-changes/${sceneChangeId}/acknowledge`,
    { method: 'POST' }
  );
}

// ============================================================================
// Scene Change Summary Types and Functions (NEM-3580)
// ============================================================================

/**
 * Scene change types for categorization.
 */
export type SceneChangeType = 'view_blocked' | 'angle_changed' | 'view_tampered' | 'unknown';

/**
 * Breakdown of scene changes by type.
 */
export interface SceneChangeTypeBreakdown {
  /** Type of scene change */
  type: SceneChangeType;
  /** Number of changes of this type */
  count: number;
  /** Percentage of total changes */
  percentage: number;
}

/**
 * Summary statistics for scene changes.
 *
 * Provides aggregated data computed from the scene change list,
 * enabling summary dashboards and trend analysis.
 */
export interface SceneChangeSummary {
  /** Camera ID */
  cameraId: string;
  /** Total number of scene changes in the period */
  totalChanges: number;
  /** Number of unacknowledged changes */
  unacknowledgedCount: number;
  /** Number of acknowledged changes */
  acknowledgedCount: number;
  /** Most recent scene change timestamp (ISO 8601), null if no changes */
  lastChangeAt: string | null;
  /** Oldest scene change in the data set (ISO 8601), null if no changes */
  firstChangeAt: string | null;
  /** Breakdown of changes by type */
  byType: SceneChangeTypeBreakdown[];
  /** Average similarity score (0-1) */
  avgSimilarityScore: number | null;
  /** Most common change type, null if no changes */
  mostCommonType: SceneChangeType | null;
  /** Number of days covered by the data */
  periodDays: number;
}

/**
 * Options for fetching scene change summary.
 */
export interface SceneChangeSummaryOptions {
  /** Number of days to look back (default: 7) */
  days?: number;
}

/**
 * Fetch scene change summary statistics for a camera.
 *
 * This function fetches all scene changes for a camera (up to a reasonable limit)
 * and computes summary statistics client-side. The summary includes:
 * - Total count and acknowledgement breakdown
 * - Most recent change timestamp
 * - Breakdown by change type
 * - Average similarity score
 *
 * Note: This is computed client-side from the list endpoint since there's no
 * dedicated backend summary endpoint. For cameras with many scene changes,
 * consider using pagination or implementing a backend aggregation endpoint.
 *
 * @param cameraId - Camera ID to fetch summary for
 * @param options - Optional query parameters
 * @returns SceneChangeSummary with aggregated statistics
 *
 * @example
 * ```typescript
 * const summary = await fetchSceneChangeSummary('front_door', { days: 30 });
 * console.log(`${summary.totalChanges} changes, ${summary.unacknowledgedCount} need review`);
 *
 * // Show breakdown by type
 * summary.byType.forEach(({ type, count, percentage }) => {
 *   console.log(`${type}: ${count} (${percentage.toFixed(1)}%)`);
 * });
 * ```
 */
export async function fetchSceneChangeSummary(
  cameraId: string,
  options?: SceneChangeSummaryOptions
): Promise<SceneChangeSummary> {
  const days = options?.days ?? 7;

  // Fetch all scene changes (use high limit to get comprehensive data)
  // For a proper implementation, a backend summary endpoint would be more efficient
  const response = await fetchSceneChanges(cameraId, { limit: 100 });

  const changes = response.scene_changes ?? [];

  // Filter by date range if days is specified
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);
  const recentChanges = changes.filter(
    (sc) => new Date(sc.detected_at) >= cutoffDate
  );

  // Compute summary statistics
  const totalChanges = recentChanges.length;
  const unacknowledgedCount = recentChanges.filter((sc) => !sc.acknowledged).length;
  const acknowledgedCount = totalChanges - unacknowledgedCount;

  // Find timestamps
  let lastChangeAt: string | null = null;
  let firstChangeAt: string | null = null;
  if (recentChanges.length > 0) {
    // Changes are already sorted by detected_at descending
    lastChangeAt = recentChanges[0].detected_at;
    firstChangeAt = recentChanges[recentChanges.length - 1].detected_at;
  }

  // Compute type breakdown
  const typeCountMap = new Map<SceneChangeType, number>();
  for (const sc of recentChanges) {
    const type = sc.change_type as SceneChangeType;
    typeCountMap.set(type, (typeCountMap.get(type) ?? 0) + 1);
  }

  const byType: SceneChangeTypeBreakdown[] = Array.from(typeCountMap.entries())
    .map(([type, count]) => ({
      type,
      count,
      percentage: totalChanges > 0 ? (count / totalChanges) * 100 : 0,
    }))
    .sort((a, b) => b.count - a.count);

  // Find most common type
  const mostCommonType: SceneChangeType | null =
    byType.length > 0 ? byType[0].type : null;

  // Compute average similarity score
  let avgSimilarityScore: number | null = null;
  if (recentChanges.length > 0) {
    const totalScore = recentChanges.reduce((sum, sc) => sum + sc.similarity_score, 0);
    avgSimilarityScore = totalScore / recentChanges.length;
  }

  return {
    cameraId,
    totalChanges,
    unacknowledgedCount,
    acknowledgedCount,
    lastChangeAt,
    firstChangeAt,
    byType,
    avgSimilarityScore,
    mostCommonType,
    periodDays: days,
  };
}

// ============================================================================
// A/B Testing Types
// ============================================================================

/**
 * Result from an A/B test comparing two prompts on a single event.
 *
 * Used by the PromptABTest component to display side-by-side comparison
 * of original vs modified prompt performance on real events.
 */
export interface ABTestResult {
  /** The event ID that was tested */
  eventId: number;
  /** Result from the original (A) prompt */
  originalResult: {
    /** Risk score from original prompt (0-100) */
    riskScore: number;
    /** Risk level classification (low, medium, high, critical) */
    riskLevel: string;
    /** LLM reasoning output */
    reasoning: string;
    /** Time taken for inference in milliseconds */
    processingTimeMs: number;
  };
  /** Result from the modified (B) prompt */
  modifiedResult: {
    /** Risk score from modified prompt (0-100) */
    riskScore: number;
    /** Risk level classification (low, medium, high, critical) */
    riskLevel: string;
    /** LLM reasoning output */
    reasoning: string;
    /** Time taken for inference in milliseconds */
    processingTimeMs: number;
  };
  /** Score difference: modified - original (negative = B produces lower risk) */
  scoreDelta: number;
}

// ============================================================================
// Event Clip Types
// ============================================================================

/**
 * Status of clip generation
 */
export type ClipStatus = 'pending' | 'completed' | 'failed';

/**
 * Response from GET /api/events/{event_id}/clip
 */
export interface ClipInfoResponse {
  event_id: number;
  clip_available: boolean;
  clip_url: string | null;
  duration_seconds: number | null;
  generated_at: string | null;
  file_size_bytes: number | null;
}

/**
 * Request for POST /api/events/{event_id}/clip/generate
 */
export interface ClipGenerateRequest {
  start_offset_seconds?: number;
  end_offset_seconds?: number;
  force?: boolean;
}

/**
 * Response from POST /api/events/{event_id}/clip/generate
 */
export interface ClipGenerateResponse {
  event_id: number;
  status: ClipStatus;
  clip_url: string | null;
  generated_at: string | null;
  message: string | null;
}

// ============================================================================
// Event Clip Endpoints
// ============================================================================

/**
 * Get clip information for a specific event.
 *
 * Returns information about whether a video clip is available for the event,
 * and if available, provides the URL to access it along with metadata.
 *
 * @param eventId - The ID of the event
 * @returns ClipInfoResponse with clip availability and metadata
 */
export async function fetchEventClipInfo(eventId: number): Promise<ClipInfoResponse> {
  return fetchApi<ClipInfoResponse>(`/api/events/${eventId}/clip`);
}

/**
 * Trigger video clip generation for an event.
 *
 * If a clip already exists and force=false, returns the existing clip info.
 * If force=true, regenerates the clip even if one exists.
 *
 * @param eventId - The ID of the event
 * @param request - Clip generation parameters (optional)
 * @returns ClipGenerateResponse with generation status and clip info
 */
export async function generateEventClip(
  eventId: number,
  request?: ClipGenerateRequest
): Promise<ClipGenerateResponse> {
  return fetchApi<ClipGenerateResponse>(`/api/events/${eventId}/clip/generate`, {
    method: 'POST',
    body: JSON.stringify(request || {}),
  });
}

/**
 * Get the URL for an event clip video.
 * This URL can be used directly in a video src attribute.
 *
 * Note: Media endpoints are exempt from API key authentication.
 *
 * @param clipFilename - The clip filename (from ClipInfoResponse.clip_url)
 * @returns The full URL to the clip video endpoint
 */
export function getEventClipUrl(clipFilename: string): string {
  // clip_url from API is already in the format "/api/media/clips/{filename}"
  // If it starts with /api, prepend BASE_URL; otherwise assume it's a full path
  if (clipFilename.startsWith('/api/')) {
    return `${BASE_URL}${clipFilename}`;
  }
  return clipFilename;
}

// ============================================================================
// Entity Re-Identification Endpoints
// ============================================================================

/**
 * Query parameters for listing tracked entities.
 */
export interface EntityQueryParams {
  /** Filter by entity type: 'person' or 'vehicle' */
  entity_type?: 'person' | 'vehicle';
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter entities seen since this ISO timestamp */
  since?: string;
  /** Maximum number of results (1-1000, default 50) */
  limit?: number;
  /**
   * Cursor for pagination. Pass the `next_cursor` value from the previous response.
   */
  cursor?: string;
}

/**
 * Fetch a paginated list of tracked entities.
 *
 * Returns entities that have been tracked via re-identification across cameras.
 * Entities are grouped by their embedding clusters and sorted by last_seen (newest first).
 *
 * @param params - Optional query parameters for filtering
 * @returns EntityListResponse with filtered entities and pagination info
 *
 * @example
 * ```typescript
 * // Fetch all entities
 * const entities = await fetchTrackedEntities();
 *
 * // Fetch only persons seen on front_door camera
 * const persons = await fetchTrackedEntities({
 *   entity_type: 'person',
 *   camera_id: 'front_door',
 * });
 *
 * // Fetch entities seen in the last hour
 * const recent = await fetchTrackedEntities({
 *   since: new Date(Date.now() - 3600000).toISOString(),
 * });
 * ```
 */
export async function fetchTrackedEntities(
  params?: EntityQueryParams
): Promise<EntityListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.entity_type) {
    searchParams.append('entity_type', params.entity_type);
  }
  if (params?.camera_id) {
    searchParams.append('camera_id', params.camera_id);
  }
  if (params?.since) {
    searchParams.append('since', params.since);
  }
  if (params?.limit !== undefined) {
    searchParams.append('limit', String(params.limit));
  }
  if (params?.cursor) {
    searchParams.append('cursor', params.cursor);
  }

  const queryString = searchParams.toString();
  const endpoint = queryString ? `/api/entities?${queryString}` : '/api/entities';

  return fetchApi<EntityListResponse>(endpoint);
}

/**
 * Fetch detailed information about a specific entity.
 *
 * Returns the entity's summary information along with all recorded appearances
 * across all cameras. The appearances are sorted chronologically.
 *
 * @param entityId - Unique entity identifier (detection_id)
 * @returns EntityDetail with full entity information and appearances
 * @throws ApiError with status 404 if entity not found
 * @throws ApiError with status 503 if Redis service is unavailable
 *
 * @example
 * ```typescript
 * try {
 *   const entity = await fetchEntityDetails('det_abc123');
 *   console.log(`Entity ${entity.id} has ${entity.appearance_count} appearances`);
 *   console.log(`Cameras seen: ${entity.cameras_seen?.join(', ')}`);
 * } catch (error) {
 *   if (error instanceof ApiError && error.status === 404) {
 *     console.log('Entity not found');
 *   }
 * }
 * ```
 */
export async function fetchEntityDetails(entityId: string): Promise<EntityDetail> {
  return fetchApi<EntityDetail>(`/api/entities/${encodeURIComponent(entityId)}`);
}

// ============================================================================
// Event Feedback API (additional functions)
// ============================================================================

/**
 * Get feedback for a specific event.
 *
 * @param eventId - The event ID to get feedback for
 * @returns The feedback record for the event
 * @throws ApiError with status 404 if no feedback exists for the event
 *
 * @example
 * ```typescript
 * try {
 *   const feedback = await fetchEventFeedback(123);
 *   console.log(`Event ${feedback.event_id} was marked as ${feedback.feedback_type}`);
 * } catch (error) {
 *   if (error instanceof ApiError && error.status === 404) {
 *     console.log('No feedback for this event yet');
 *   }
 * }
 * ```
 */
export async function fetchEventFeedback(eventId: number): Promise<EventFeedbackResponse> {
  return fetchApi<EventFeedbackResponse>(`/api/feedback/event/${eventId}`);
}

/**
 * Get aggregate feedback statistics.
 *
 * Returns counts of feedback grouped by type and camera.
 * Useful for tracking model accuracy and identifying cameras with high false positive rates.
 *
 * @returns Aggregate statistics including total count and breakdowns by type/camera
 *
 * @example
 * ```typescript
 * const stats = await fetchFeedbackStats();
 * console.log(`Total feedback: ${stats.total_feedback}`);
 * console.log(`False positives: ${stats.by_type.false_positive || 0}`);
 * ```
 */
export async function fetchFeedbackStats(): Promise<FeedbackStatsResponse> {
  return fetchApi<FeedbackStatsResponse>('/api/feedback/stats');
}

// ============================================================================
// Calibration Endpoints
// ============================================================================

/**
 * Fetch the current user's calibration settings.
 *
 * Returns the calibration thresholds and feedback statistics.
 * Creates a default calibration if none exists.
 *
 * @returns CalibrationResponse with current calibration data
 *
 * @example
 * ```typescript
 * const calibration = await fetchCalibration();
 * console.log(`Low threshold: ${calibration.low_threshold}`);
 * console.log(`Medium threshold: ${calibration.medium_threshold}`);
 * console.log(`High threshold: ${calibration.high_threshold}`);
 * ```
 */
export async function fetchCalibration(): Promise<CalibrationResponse> {
  return fetchApi<CalibrationResponse>('/api/calibration');
}

/**
 * Update calibration thresholds.
 *
 * Allows partial updates - only provided fields will be changed.
 * Validates that threshold ordering is maintained (low < medium < high).
 *
 * @param update - CalibrationUpdate with fields to update
 * @returns CalibrationResponse with updated calibration data
 * @throws ApiError if threshold ordering would be violated (422)
 *
 * @example
 * ```typescript
 * const updated = await updateCalibration({
 *   low_threshold: 35,
 *   medium_threshold: 58,
 * });
 * console.log(`Updated thresholds: ${updated.low_threshold}, ${updated.medium_threshold}`);
 * ```
 */
export async function updateCalibration(update: CalibrationUpdate): Promise<CalibrationResponse> {
  return fetchApi<CalibrationResponse>('/api/calibration', {
    method: 'PUT',
    body: JSON.stringify(update),
  });
}

/**
 * Reset calibration to default thresholds.
 *
 * Resets all thresholds to their default values:
 * - low_threshold: 30
 * - medium_threshold: 60
 * - high_threshold: 85
 * - decay_factor: 0.1
 *
 * Note: Feedback counts (false_positive_count, missed_threat_count)
 * are NOT reset by this operation.
 *
 * @returns CalibrationResetResponse with success message and reset calibration
 *
 * @example
 * ```typescript
 * const result = await resetCalibration();
 * console.log(result.message); // "Calibration reset to default values"
 * console.log(`New low threshold: ${result.calibration.low_threshold}`);
 * ```
 */
export async function resetCalibration(): Promise<CalibrationResetResponse> {
  return fetchApi<CalibrationResetResponse>('/api/calibration/reset', {
    method: 'POST',
  });
}

/**
 * Get default calibration threshold values.
 *
 * Returns the default values used when creating new calibrations
 * or when resetting to defaults. Useful for displaying defaults in the UI.
 *
 * @returns CalibrationDefaultsResponse with default threshold values
 *
 * @example
 * ```typescript
 * const defaults = await fetchCalibrationDefaults();
 * console.log(`Default low: ${defaults.low_threshold}`);
 * console.log(`Default medium: ${defaults.medium_threshold}`);
 * console.log(`Default high: ${defaults.high_threshold}`);
 * ```
 */
export async function fetchCalibrationDefaults(): Promise<CalibrationDefaultsResponse> {
  return fetchApi<CalibrationDefaultsResponse>('/api/calibration/defaults');
}

// ============================================================================
// Entity Re-Identification V2 API (Historical + Real-time)
// ============================================================================

/**
 * Source filter for entity queries.
 * Controls which storage backend to query:
 * - redis: Only query Redis hot cache (24h window)
 * - postgres: Only query PostgreSQL (30d retention)
 * - both: Query both and merge results (default)
 */
export type SourceFilter = 'redis' | 'postgres' | 'both';

/**
 * Query parameters for the v2 entities endpoint.
 * Supports historical queries from PostgreSQL and real-time from Redis.
 */
export interface EntitiesV2QueryParams {
  /** Filter by entity type: 'person' or 'vehicle' */
  entity_type?: 'person' | 'vehicle';
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter entities seen since this ISO timestamp */
  since?: string;
  /** Filter entities seen until this ISO timestamp */
  until?: string;
  /** Data source: 'redis', 'postgres', or 'both' (default: 'both') */
  source?: SourceFilter;
  /** Maximum number of results (1-1000, default 50) */
  limit?: number;
  /** Number of results to skip for pagination (default 0) */
  offset?: number;
}

/**
 * Detection summary for entity detections list.
 */
export interface DetectionSummary {
  detection_id: number;
  camera_id: string;
  camera_name: string | null;
  timestamp: string;
  confidence: number | null;
  thumbnail_url: string | null;
  object_type: string | null;
}

/**
 * Response for entity detections list endpoint.
 */
export interface EntityDetectionsResponse {
  entity_id: string;
  entity_type: string;
  detections: DetectionSummary[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

/**
 * Response for entity statistics endpoint.
 */
export interface EntityStatsResponse {
  total_entities: number;
  total_appearances: number;
  by_type: Record<string, number>;
  by_camera: Record<string, number>;
  repeat_visitors: number;
  time_range?: {
    since?: string | null;
    until?: string | null;
  } | null;
}

/**
 * Fetch tracked entities from the v2 API with historical support.
 *
 * Returns a paginated list of entities from Redis (hot cache) and/or
 * PostgreSQL (historical data). Use the source parameter to control
 * which backend to query.
 *
 * @param params - Query parameters for filtering
 * @returns EntityListResponse with filtered entities and pagination info
 *
 * @example
 * ```typescript
 * // Fetch all entities from both sources
 * const entities = await fetchEntitiesV2();
 *
 * // Fetch only historical entities (PostgreSQL)
 * const historical = await fetchEntitiesV2({ source: 'postgres' });
 *
 * // Fetch entities with date range filter
 * const dateRange = await fetchEntitiesV2({
 *   since: '2024-01-01T00:00:00Z',
 *   until: '2024-01-31T23:59:59Z',
 * });
 * ```
 */
export async function fetchEntitiesV2(params?: EntitiesV2QueryParams): Promise<EntityListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.entity_type) {
    searchParams.append('entity_type', params.entity_type);
  }
  if (params?.camera_id) {
    searchParams.append('camera_id', params.camera_id);
  }
  if (params?.since) {
    searchParams.append('since', params.since);
  }
  if (params?.until) {
    searchParams.append('until', params.until);
  }
  if (params?.source) {
    searchParams.append('source', params.source);
  }
  if (params?.limit !== undefined) {
    searchParams.append('limit', String(params.limit));
  }
  if (params?.offset !== undefined) {
    searchParams.append('offset', String(params.offset));
  }

  const queryString = searchParams.toString();
  const endpoint = queryString ? `/api/entities/v2?${queryString}` : '/api/entities/v2';

  return fetchApi<EntityListResponse>(endpoint);
}

/**
 * Fetch detailed information about a specific entity from PostgreSQL.
 *
 * Returns the canonical PostgreSQL entity record with full history.
 * For real-time Redis entities, use the original fetchEntityDetails function.
 *
 * @param entityId - UUID of the entity
 * @returns EntityDetail with full entity information
 * @throws ApiError with status 404 if entity not found
 *
 * @example
 * ```typescript
 * try {
 *   const entity = await fetchEntityV2('550e8400-e29b-41d4-a716-446655440000');
 *   console.log(`Entity ${entity.id} has ${entity.appearance_count} appearances`);
 * } catch (error) {
 *   if (error instanceof ApiError && error.status === 404) {
 *     console.log('Entity not found in PostgreSQL');
 *   }
 * }
 * ```
 */
export async function fetchEntityV2(entityId: string): Promise<EntityDetail> {
  return fetchApi<EntityDetail>(`/api/entities/v2/${encodeURIComponent(entityId)}`);
}

/**
 * Fetch detections linked to a specific entity.
 *
 * Returns paginated detections associated with the specified entity.
 *
 * @param entityId - UUID of the entity
 * @param params - Pagination parameters
 * @returns EntityDetectionsResponse with linked detections and pagination info
 * @throws ApiError with status 404 if entity not found
 *
 * @example
 * ```typescript
 * const detections = await fetchEntityDetections(
 *   '550e8400-e29b-41d4-a716-446655440000',
 *   { limit: 20, offset: 0 }
 * );
 * console.log(`Found ${detections.pagination.total} detections`);
 * ```
 */
export async function fetchEntityDetections(
  entityId: string,
  params?: { limit?: number; offset?: number }
): Promise<EntityDetectionsResponse> {
  const searchParams = new URLSearchParams();

  if (params?.limit !== undefined) {
    searchParams.append('limit', String(params.limit));
  }
  if (params?.offset !== undefined) {
    searchParams.append('offset', String(params.offset));
  }

  const queryString = searchParams.toString();
  const endpoint = queryString
    ? `/api/entities/v2/${encodeURIComponent(entityId)}/detections?${queryString}`
    : `/api/entities/v2/${encodeURIComponent(entityId)}/detections`;

  return fetchApi<EntityDetectionsResponse>(endpoint);
}

/**
 * Fetch aggregated entity statistics.
 *
 * Returns statistics about tracked entities including counts by type,
 * camera, and repeat visitors.
 *
 * @param params - Optional time range filter
 * @returns EntityStatsResponse with aggregated statistics
 *
 * @example
 * ```typescript
 * // Get all-time statistics
 * const stats = await fetchEntityStats();
 * console.log(`Total entities: ${stats.total_entities}`);
 * console.log(`Repeat visitors: ${stats.repeat_visitors}`);
 *
 * // Get statistics for a specific time range
 * const rangeStats = await fetchEntityStats({
 *   since: '2024-01-01T00:00:00Z',
 *   until: '2024-01-31T23:59:59Z',
 * });
 * ```
 */
export async function fetchEntityStats(params?: {
  since?: string;
  until?: string;
}): Promise<EntityStatsResponse> {
  const searchParams = new URLSearchParams();

  if (params?.since) {
    searchParams.append('since', params.since);
  }
  if (params?.until) {
    searchParams.append('until', params.until);
  }

  const queryString = searchParams.toString();
  const endpoint = queryString ? `/api/entities/stats?${queryString}` : '/api/entities/stats';

  return fetchApi<EntityStatsResponse>(endpoint);
}

// ============================================================================
// Entity Trust Classification API
// ============================================================================

/**
 * Update an entity's trust classification status.
 *
 * Allows marking entities as trusted (known/safe), untrusted (suspicious),
 * or unclassified (default). Includes optional notes for documenting
 * the classification decision.
 *
 * @param entityId - UUID of the entity to update
 * @param trustStatus - The trust classification to assign
 * @param notes - Optional notes explaining the classification decision
 * @returns EntityTrustResponse with updated trust information
 * @throws ApiError with status 404 if entity not found
 *
 * @example
 * ```typescript
 * // Mark entity as trusted
 * const result = await updateEntityTrust(
 *   '550e8400-e29b-41d4-a716-446655440000',
 *   'trusted',
 *   'Regular mail carrier, verified by homeowner'
 * );
 * console.log(`Entity marked as: ${result.trust_status}`);
 *
 * // Mark entity as untrusted (suspicious)
 * await updateEntityTrust(entityId, 'untrusted', 'Unknown person at night');
 *
 * // Reset to unclassified
 * await updateEntityTrust(entityId, 'unclassified');
 * ```
 */
export async function updateEntityTrust(
  entityId: string,
  trustStatus: TrustStatus,
  notes?: string
): Promise<EntityTrustResponse> {
  const body: EntityTrustUpdate = {
    trust_status: trustStatus,
    notes: notes ?? null,
  };

  return fetchApi<EntityTrustResponse>(`/api/entities/${encodeURIComponent(entityId)}/trust`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
}

/**
 * Fetch list of trusted entities.
 *
 * Returns a paginated list of entities that have been marked as trusted.
 *
 * @param params - Optional filter and pagination parameters
 * @returns TrustedEntityListResponse with trusted entities and pagination info
 *
 * @example
 * ```typescript
 * // Get all trusted entities
 * const trusted = await fetchTrustedEntities();
 * console.log(`Found ${trusted.items.length} trusted entities`);
 *
 * // Get trusted persons only
 * const trustedPersons = await fetchTrustedEntities({ entity_type: 'person' });
 * ```
 */
export async function fetchTrustedEntities(params?: {
  entity_type?: 'person' | 'vehicle';
  limit?: number;
  offset?: number;
}): Promise<TrustedEntityListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.entity_type) {
    searchParams.append('entity_type', params.entity_type);
  }
  if (params?.limit) {
    searchParams.append('limit', params.limit.toString());
  }
  if (params?.offset) {
    searchParams.append('offset', params.offset.toString());
  }

  const queryString = searchParams.toString();
  const endpoint = queryString ? `/api/entities/trusted?${queryString}` : '/api/entities/trusted';

  return fetchApi<TrustedEntityListResponse>(endpoint);
}

/**
 * Fetch list of untrusted (suspicious) entities.
 *
 * Returns a paginated list of entities that have been marked as untrusted.
 *
 * @param params - Optional filter and pagination parameters
 * @returns TrustedEntityListResponse with untrusted entities and pagination info
 *
 * @example
 * ```typescript
 * // Get all untrusted entities
 * const suspicious = await fetchUntrustedEntities();
 * console.log(`Found ${suspicious.items.length} suspicious entities`);
 * ```
 */
export async function fetchUntrustedEntities(params?: {
  entity_type?: 'person' | 'vehicle';
  limit?: number;
  offset?: number;
}): Promise<TrustedEntityListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.entity_type) {
    searchParams.append('entity_type', params.entity_type);
  }
  if (params?.limit) {
    searchParams.append('limit', params.limit.toString());
  }
  if (params?.offset) {
    searchParams.append('offset', params.offset.toString());
  }

  const queryString = searchParams.toString();
  const endpoint = queryString
    ? `/api/entities/untrusted?${queryString}`
    : '/api/entities/untrusted';

  return fetchApi<TrustedEntityListResponse>(endpoint);
}

// ============================================================================
// Analytics API Functions
// ============================================================================

/**
 * Fetch detection trends for a date range.
 *
 * Returns daily detection counts aggregated by day for the specified date range.
 * Creates one data point per day even if there are no detections (count=0).
 *
 * @param params - Date range parameters
 * @returns DetectionTrendsResponse with daily detection counts
 *
 * @example
 * ```typescript
 * // Get detection trends for the last 7 days
 * const endDate = new Date().toISOString().split('T')[0];
 * const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
 * const trends = await fetchDetectionTrends({ start_date: startDate, end_date: endDate });
 * console.log(`Total detections: ${trends.total_detections}`);
 * trends.data_points.forEach(point => {
 *   console.log(`${point.date}: ${point.count} detections`);
 * });
 * ```
 */
export async function fetchDetectionTrends(
  params: DetectionTrendsParams
): Promise<DetectionTrendsResponse> {
  const searchParams = new URLSearchParams();
  searchParams.append('start_date', params.start_date);
  searchParams.append('end_date', params.end_date);

  return fetchApi<DetectionTrendsResponse>(
    `/api/analytics/detection-trends?${searchParams.toString()}`
  );
}

/**
 * Fetch risk history for a date range.
 *
 * Returns daily event counts grouped by risk level (low, medium, high, critical)
 * for the specified date range. Creates one data point per day even if there
 * are no events (all counts = 0).
 *
 * @param params - Date range parameters with start_date and end_date
 * @returns RiskHistoryResponse with daily risk level counts
 *
 * @example
 * ```typescript
 * // Get risk history for the last 7 days
 * const endDate = new Date().toISOString().split('T')[0];
 * const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
 * const history = await fetchRiskHistory({ start_date: startDate, end_date: endDate });
 * history.data_points.forEach(point => {
 *   console.log(`${point.date}: low=${point.low}, medium=${point.medium}, high=${point.high}, critical=${point.critical}`);
 * });
 * ```
 */
export async function fetchRiskHistory(
  params: RiskHistoryQueryParams
): Promise<RiskHistoryResponse> {
  const searchParams = new URLSearchParams();
  searchParams.append('start_date', params.start_date);
  searchParams.append('end_date', params.end_date);

  return fetchApi<RiskHistoryResponse>(`/api/analytics/risk-history?${searchParams.toString()}`);
}

/**
 * Query parameters for the camera uptime endpoint.
 */
export interface CameraUptimeParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
}

/**
 * Fetch camera uptime data for a date range.
 *
 * Returns uptime percentage and detection count for each camera.
 * Uptime is calculated based on the number of days with at least one detection
 * divided by the total days in the date range.
 *
 * @param params - Date range parameters
 * @returns CameraUptimeResponse with per-camera uptime data
 *
 * @example
 * ```typescript
 * // Get camera uptime for the last 30 days
 * const endDate = new Date().toISOString().split('T')[0];
 * const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
 * const uptime = await fetchCameraUptime({ start_date: startDate, end_date: endDate });
 * uptime.cameras.forEach(cam => {
 *   console.log(`${cam.camera_name}: ${cam.uptime_percentage}% uptime`);
 * });
 * ```
 */
export async function fetchCameraUptime(params: CameraUptimeParams): Promise<CameraUptimeResponse> {
  const searchParams = new URLSearchParams();
  searchParams.append('start_date', params.start_date);
  searchParams.append('end_date', params.end_date);

  return fetchApi<CameraUptimeResponse>(`/api/analytics/camera-uptime?${searchParams.toString()}`);
}

/**
 * Query parameters for the object distribution endpoint.
 */
export interface ObjectDistributionParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
}

/**
 * Fetch object distribution for a date range.
 *
 * Returns detection counts grouped by object type (person, car, etc.)
 * for the specified date range. Includes percentage of total detections.
 *
 * @param params - Date range parameters with start_date and end_date
 * @returns ObjectDistributionResponse with object type breakdown
 *
 * @example
 * ```typescript
 * // Get object distribution for the last 7 days
 * const endDate = new Date().toISOString().split('T')[0];
 * const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
 * const distribution = await fetchObjectDistribution({ start_date: startDate, end_date: endDate });
 * distribution.object_types.forEach(obj => {
 *   console.log(`${obj.object_type}: ${obj.count} (${obj.percentage.toFixed(1)}%)`);
 * });
 * ```
 */
export async function fetchObjectDistribution(
  params: ObjectDistributionParams
): Promise<ObjectDistributionResponse> {
  const searchParams = new URLSearchParams();
  searchParams.append('start_date', params.start_date);
  searchParams.append('end_date', params.end_date);

  return fetchApi<ObjectDistributionResponse>(
    `/api/analytics/object-distribution?${searchParams.toString()}`
  );
}

// ============================================================================
// Risk Score Distribution API (NEM-3602)
// ============================================================================

/**
 * Query parameters for the risk score distribution endpoint.
 */
export interface RiskScoreDistributionParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
  /** Size of each bucket (default: 10) */
  bucket_size?: number;
}

/**
 * A single bucket in the risk score distribution histogram.
 */
export interface RiskScoreDistributionBucket {
  /** Minimum score in this bucket (inclusive) */
  min_score: number;
  /** Maximum score in this bucket (exclusive, except last bucket includes 100) */
  max_score: number;
  /** Number of events in this bucket */
  count: number;
}

/**
 * Response from GET /api/analytics/risk-score-distribution endpoint.
 */
export interface RiskScoreDistributionResponse {
  /** Risk score distribution buckets */
  buckets: RiskScoreDistributionBucket[];
  /** Total events with risk scores in date range */
  total_events: number;
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
  /** Size of each bucket */
  bucket_size: number;
}

/**
 * Fetch risk score distribution for a date range.
 *
 * Returns a histogram of events grouped by risk score buckets.
 * Includes events with non-null risk scores only.
 *
 * @param params - Date range parameters with optional bucket_size
 * @returns RiskScoreDistributionResponse with histogram buckets
 *
 * @example
 * ```typescript
 * // Get risk score distribution for the last 7 days
 * const endDate = new Date().toISOString().split('T')[0];
 * const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
 * const distribution = await fetchRiskScoreDistribution({ start_date: startDate, end_date: endDate });
 * distribution.buckets.forEach(bucket => {
 *   console.log(`${bucket.min_score}-${bucket.max_score}: ${bucket.count} events`);
 * });
 * ```
 */
export async function fetchRiskScoreDistribution(
  params: RiskScoreDistributionParams
): Promise<RiskScoreDistributionResponse> {
  const searchParams = new URLSearchParams();
  searchParams.append('start_date', params.start_date);
  searchParams.append('end_date', params.end_date);
  if (params.bucket_size !== undefined) {
    searchParams.append('bucket_size', params.bucket_size.toString());
  }

  return fetchApi<RiskScoreDistributionResponse>(
    `/api/analytics/risk-score-distribution?${searchParams.toString()}`
  );
}

// ============================================================================
// Risk Score Trends API (NEM-3602)
// ============================================================================

/**
 * Query parameters for the risk score trends endpoint.
 */
export interface RiskScoreTrendsParams {
  /** Start date in ISO format (YYYY-MM-DD) */
  start_date: string;
  /** End date in ISO format (YYYY-MM-DD) */
  end_date: string;
}

/**
 * A single data point in the risk score trends response.
 */
export interface RiskScoreTrendDataPoint {
  /** Date in ISO format (YYYY-MM-DD) */
  date: string;
  /** Average risk score on this date */
  avg_score: number;
  /** Number of events on this date */
  count: number;
}

/**
 * Response from GET /api/analytics/risk-score-trends endpoint.
 */
export interface RiskScoreTrendsResponse {
  /** Average risk score aggregated by day */
  data_points: RiskScoreTrendDataPoint[];
  /** Start date of the range (ISO format) */
  start_date: string;
  /** End date of the range (ISO format) */
  end_date: string;
}

/**
 * Fetch risk score trends for a date range.
 *
 * Returns daily average risk scores for the specified date range.
 * Creates one data point per day even if there are no events.
 *
 * @param params - Date range parameters
 * @returns RiskScoreTrendsResponse with daily average scores
 *
 * @example
 * ```typescript
 * // Get risk score trends for the last 7 days
 * const endDate = new Date().toISOString().split('T')[0];
 * const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
 * const trends = await fetchRiskScoreTrends({ start_date: startDate, end_date: endDate });
 * trends.data_points.forEach(point => {
 *   console.log(`${point.date}: avg=${point.avg_score.toFixed(1)}, count=${point.count}`);
 * });
 * ```
 */
export async function fetchRiskScoreTrends(
  params: RiskScoreTrendsParams
): Promise<RiskScoreTrendsResponse> {
  const searchParams = new URLSearchParams();
  searchParams.append('start_date', params.start_date);
  searchParams.append('end_date', params.end_date);

  return fetchApi<RiskScoreTrendsResponse>(
    `/api/analytics/risk-score-trends?${searchParams.toString()}`
  );
}

// ============================================================================
// Request Recording API (NEM-2721)
// ============================================================================

export type { RecordingResponse, RecordingsListResponse, ReplayResponse };

/**
 * Recording detail response includes headers, body, and response data.
 * This extends the RecordingResponse with additional fields returned by GET /api/debug/recordings/{id}
 */
export interface RecordingDetailResponse extends RecordingResponse {
  /** Request headers */
  headers?: Record<string, string>;
  /** Request query parameters */
  query_params?: Record<string, string>;
  /** Request body (if any) */
  body?: unknown;
  /** Original response body */
  response_body?: unknown;
  /** Original response headers */
  response_headers?: Record<string, string>;
  /** When the recording was retrieved */
  retrieved_at?: string;
}

/**
 * Fetch list of recorded requests.
 *
 * Returns all recorded API requests sorted by timestamp (newest first).
 * Only available when debug mode is enabled.
 *
 * @param limit - Maximum number of recordings to return (default: 100)
 * @returns RecordingsListResponse with recording metadata
 *
 * @example
 * ```typescript
 * const { recordings, total } = await fetchRecordings();
 * console.log(`Found ${total} recordings`);
 * ```
 */
export async function fetchRecordings(limit: number = 100): Promise<RecordingsListResponse> {
  const endpoint = limit !== 100 ? `/api/debug/recordings?limit=${limit}` : '/api/debug/recordings';
  return fetchApi<RecordingsListResponse>(endpoint);
}

/**
 * Fetch details of a specific recording.
 *
 * Returns the full recording data including headers, body, and response.
 * Only available when debug mode is enabled.
 *
 * @param recordingId - ID of the recording to retrieve
 * @returns RecordingDetailResponse with full request/response data
 *
 * @example
 * ```typescript
 * const recording = await fetchRecordingDetail('abc-123');
 * console.log(`Request: ${recording.method} ${recording.path}`);
 * ```
 */
export async function fetchRecordingDetail(recordingId: string): Promise<RecordingDetailResponse> {
  return fetchApi<RecordingDetailResponse>(
    `/api/debug/recordings/${encodeURIComponent(recordingId)}`
  );
}

/**
 * Replay a recorded request.
 *
 * Reconstructs and executes the original request against the current server.
 * Returns both the original and replay responses for comparison.
 * Only available when debug mode is enabled.
 *
 * @param recordingId - ID of the recording to replay
 * @returns ReplayResponse with original vs replay comparison
 *
 * @example
 * ```typescript
 * const result = await replayRecording('abc-123');
 * if (result.original_status_code !== result.replay_status_code) {
 *   console.log('Status code changed!');
 * }
 * ```
 */
export async function replayRecording(recordingId: string): Promise<ReplayResponse> {
  return fetchApi<ReplayResponse>(`/api/debug/replay/${encodeURIComponent(recordingId)}`, {
    method: 'POST',
  });
}

/**
 * Delete a specific recording.
 *
 * Removes the recording file from the server.
 * Only available when debug mode is enabled.
 *
 * @param recordingId - ID of the recording to delete
 * @returns Confirmation message
 *
 * @example
 * ```typescript
 * await deleteRecording('abc-123');
 * console.log('Recording deleted');
 * ```
 */
export async function deleteRecording(recordingId: string): Promise<{ message: string }> {
  return fetchApi<{ message: string }>(`/api/debug/recordings/${encodeURIComponent(recordingId)}`, {
    method: 'DELETE',
  });
}

/**
 * Delete all recordings.
 *
 * Clears all recorded requests from the server.
 * Only available when debug mode is enabled.
 *
 * @returns Confirmation message with count of deleted recordings
 *
 * @example
 * ```typescript
 * const result = await clearAllRecordings();
 * console.log(result.message); // "Deleted 15 recordings"
 * ```
 */
export async function clearAllRecordings(): Promise<{ message: string; deleted_count: number }> {
  return fetchApi<{ message: string; deleted_count: number }>('/api/debug/recordings', {
    method: 'DELETE',
  });
}

// ============================================================================
// Debug Configuration and Log Level API (NEM-2722)
// ============================================================================

/**
 * Debug configuration response containing all config key-value pairs.
 * Sensitive values are shown as '[REDACTED]'.
 */
export type DebugConfigResponse = Record<string, unknown>;

/**
 * Current log level response.
 */
export interface LogLevelResponse {
  /** Current log level */
  level: string;
}

/**
 * Response after setting the log level.
 */
export interface SetLogLevelResponse {
  /** New log level */
  level: string;
  /** Previous log level */
  previous_level: string;
  /** Success message */
  message: string;
}

/**
 * Fetch the current application configuration.
 *
 * Returns all configuration key-value pairs with sensitive values
 * shown as '[REDACTED]'. This is a read-only endpoint.
 *
 * @returns DebugConfigResponse with all config values
 *
 * @example
 * ```typescript
 * const config = await fetchDebugConfig();
 * console.log(config.log_level); // "INFO"
 * console.log(config.database_url); // "[REDACTED]"
 * ```
 */
export async function fetchDebugConfig(): Promise<DebugConfigResponse> {
  return fetchApi<DebugConfigResponse>('/api/debug/config');
}

/**
 * Fetch the current log level.
 *
 * @returns LogLevelResponse with current level
 *
 * @example
 * ```typescript
 * const { level } = await fetchLogLevel();
 * console.log(level); // "INFO"
 * ```
 */
export async function fetchLogLevel(): Promise<LogLevelResponse> {
  return fetchApi<LogLevelResponse>('/api/debug/log-level');
}

/**
 * Set the application log level.
 *
 * Note: Changes do not persist on server restart.
 *
 * @param level - The new log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
 * @returns SetLogLevelResponse with new level and confirmation
 *
 * @example
 * ```typescript
 * const result = await setLogLevel('DEBUG');
 * console.log(result.message); // "Log level changed from INFO to DEBUG"
 * ```
 */
export async function setLogLevel(level: string): Promise<SetLogLevelResponse> {
  return fetchApi<SetLogLevelResponse>('/api/debug/log-level', {
    method: 'POST',
    body: JSON.stringify({ level }),
  });
}

// ============================================================================
// Performance Profiling API (NEM-2720)
// ============================================================================

/**
 * Individual function statistics from profiling results.
 */
export interface ProfileFunctionStats {
  /** Name of the function */
  function_name: string;
  /** Number of times the function was called */
  call_count: number;
  /** Total time spent in this function (excluding calls to subfunctions) */
  total_time: number;
  /** Cumulative time (including calls to subfunctions) */
  cumulative_time: number;
  /** Percentage of total profiling time */
  percentage: number;
}

/**
 * Profiling results with top functions by CPU time.
 */
export interface ProfileResults {
  /** Total time profiled in seconds */
  total_time: number;
  /** Top functions sorted by CPU time */
  top_functions: ProfileFunctionStats[];
}

/**
 * Current profiling status response.
 */
export interface ProfileStatusResponse {
  /** Current status: 'idle', 'profiling', or 'completed' */
  status: 'idle' | 'profiling' | 'completed';
  /** Whether profiling is currently active */
  is_profiling: boolean;
  /** Timestamp when profiling started (ISO 8601) */
  started_at: string | null;
  /** Elapsed time in seconds since profiling started */
  elapsed_seconds: number | null;
  /** Profiling results (only present when status is 'completed') */
  results: ProfileResults | null;
}

/**
 * Response from starting profiling.
 */
export interface StartProfilingResponse {
  /** Status after starting */
  status: 'profiling';
  /** Whether profiling is active */
  is_profiling: true;
  /** Timestamp when profiling started */
  started_at: string;
  /** Confirmation message */
  message: string;
}

/**
 * Response from stopping profiling.
 */
export interface StopProfilingResponse {
  /** Status after stopping */
  status: 'completed';
  /** Whether profiling is active */
  is_profiling: false;
  /** Timestamp when profiling started */
  started_at: string;
  /** Total elapsed time in seconds */
  elapsed_seconds: number;
  /** Confirmation message */
  message: string;
  /** Profiling results */
  results: ProfileResults;
}

/**
 * Fetch current profiling status.
 *
 * Returns the current state of the profiler, including whether it's active,
 * elapsed time, and results if profiling has been stopped.
 *
 * @returns ProfileStatusResponse with current status
 *
 * @example
 * ```typescript
 * const status = await fetchProfileStatus();
 * if (status.is_profiling) {
 *   console.log(`Profiling for ${status.elapsed_seconds}s`);
 * }
 * ```
 */
export async function fetchProfileStatus(): Promise<ProfileStatusResponse> {
  return fetchApi<ProfileStatusResponse>('/api/debug/profile');
}

/**
 * Start performance profiling.
 *
 * Begins profiling CPU usage across all API requests until stopped.
 * Only available when debug mode is enabled.
 *
 * @returns StartProfilingResponse with confirmation
 *
 * @example
 * ```typescript
 * const result = await startProfiling();
 * console.log(result.message); // "Profiling started"
 * ```
 */
export async function startProfiling(): Promise<StartProfilingResponse> {
  return fetchApi<StartProfilingResponse>('/api/debug/profile/start', {
    method: 'POST',
  });
}

/**
 * Stop performance profiling and get results.
 *
 * Stops profiling and returns the collected performance data,
 * including top functions by CPU time.
 *
 * @returns StopProfilingResponse with profiling results
 *
 * @example
 * ```typescript
 * const result = await stopProfiling();
 * result.results.top_functions.forEach(fn => {
 *   console.log(`${fn.function_name}: ${fn.percentage.toFixed(1)}%`);
 * });
 * ```
 */
export async function stopProfiling(): Promise<StopProfilingResponse> {
  return fetchApi<StopProfilingResponse>('/api/debug/profile/stop', {
    method: 'POST',
  });
}

/**
 * Download the profile data as a .prof file.
 *
 * Returns the raw profiling data in Python's pstats format,
 * which can be analyzed with tools like snakeviz.
 *
 * @returns Blob containing the .prof file
 *
 * @example
 * ```typescript
 * const blob = await downloadProfile();
 * const url = URL.createObjectURL(blob);
 * const a = document.createElement('a');
 * a.href = url;
 * a.download = 'profile.prof';
 * a.click();
 * ```
 */
export async function downloadProfile(): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/api/debug/profile/download`);
  if (!response.ok) {
    throw new ApiError(response.status, `Failed to download profile: ${response.statusText}`);
  }
  return response.blob();
}

// ============================================================================
// Debug Panel Enhancement API (NEM-2717)
// ============================================================================

/**
 * A single pipeline error record.
 */
export interface PipelineError {
  /** ISO timestamp of error */
  timestamp: string;
  /** Type of error (e.g., "connection_error", "timeout_error") */
  error_type: string;
  /** Component that generated the error (e.g., "detector", "analyzer") */
  component: string;
  /** Optional error message with details */
  message: string | null;
}

/**
 * Response from GET /api/debug/pipeline-errors
 */
export interface PipelineErrorsResponse {
  /** List of recent pipeline errors */
  errors: PipelineError[];
  /** Total number of errors returned */
  total: number;
  /** Maximum errors requested */
  limit: number;
  /** ISO timestamp of response */
  timestamp: string;
}

/**
 * Fetch recent pipeline errors from the debug API.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @param limit - Maximum number of errors to return (default: 10, max: 100)
 * @param component - Optional filter by component
 * @param errorType - Optional filter by error type
 * @returns Pipeline errors response
 *
 * @example
 * ```typescript
 * const errors = await fetchPipelineErrors(20, 'detector');
 * console.log(`Found ${errors.total} errors from detector`);
 * ```
 */
export async function fetchPipelineErrors(
  limit: number = 10,
  component?: string,
  errorType?: string
): Promise<PipelineErrorsResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  if (component) params.set('component', component);
  if (errorType) params.set('error_type', errorType);

  return fetchApi<PipelineErrorsResponse>(`/api/debug/pipeline-errors?${params.toString()}`);
}

/**
 * Redis info from the INFO command.
 */
export interface RedisInfo {
  /** Redis server version */
  redis_version: string;
  /** Number of connected clients */
  connected_clients: number;
  /** Human-readable used memory */
  used_memory_human: string;
  /** Human-readable peak memory usage */
  used_memory_peak_human: string;
  /** Total connections received since startup */
  total_connections_received: number;
  /** Total commands processed since startup */
  total_commands_processed: number;
  /** Uptime in seconds */
  uptime_in_seconds: number;
}

/**
 * Pub/sub channel information.
 */
export interface RedisPubsubInfo {
  /** List of active channel names */
  channels: string[];
  /** Subscriber counts per channel */
  subscriber_counts: Record<string, number>;
}

/**
 * Response from GET /api/debug/redis/info
 */
export interface RedisDebugInfoResponse {
  /** Connection status: "connected", "unavailable", or "error" */
  status: string;
  /** Redis INFO command output (null if unavailable) */
  info: RedisInfo | null;
  /** Pub/sub channel information (null if unavailable) */
  pubsub: RedisPubsubInfo | null;
  /** ISO timestamp of response */
  timestamp: string;
}

/**
 * Fetch detailed Redis information from the debug API.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @returns Redis debug info response
 *
 * @example
 * ```typescript
 * const redisInfo = await fetchRedisDebugInfo();
 * console.log(`Redis ${redisInfo.info?.redis_version} using ${redisInfo.info?.used_memory_human}`);
 * ```
 */
export async function fetchRedisDebugInfo(): Promise<RedisDebugInfoResponse> {
  return fetchApi<RedisDebugInfoResponse>('/api/debug/redis/info');
}

/**
 * Status of a WebSocket broadcaster.
 */
export interface WebSocketBroadcasterStatus {
  /** Number of active WebSocket connections */
  connection_count: number;
  /** Whether the broadcaster is listening for events */
  is_listening: boolean;
  /** Whether the broadcaster is in degraded mode */
  is_degraded: boolean;
  /** Circuit breaker state: "CLOSED", "OPEN", or "HALF_OPEN" */
  circuit_state: string;
  /** Redis channel being listened to (null for system broadcaster) */
  channel_name: string | null;
}

/**
 * Response from GET /api/debug/websocket/connections
 */
export interface WebSocketConnectionsResponse {
  /** Event broadcaster status (security event stream) */
  event_broadcaster: WebSocketBroadcasterStatus;
  /** System broadcaster status (system status stream) */
  system_broadcaster: WebSocketBroadcasterStatus;
  /** ISO timestamp of response */
  timestamp: string;
}

/**
 * Fetch WebSocket connection status from the debug API.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @returns WebSocket connections response
 *
 * @example
 * ```typescript
 * const wsStatus = await fetchWebSocketConnections();
 * const totalConnections = wsStatus.event_broadcaster.connection_count +
 *   wsStatus.system_broadcaster.connection_count;
 * console.log(`${totalConnections} active WebSocket connections`);
 * ```
 */
export async function fetchWebSocketConnections(): Promise<WebSocketConnectionsResponse> {
  return fetchApi<WebSocketConnectionsResponse>('/api/debug/websocket/connections');
}

// ============================================================================
// Summary Endpoints (Dashboard Summaries Feature - NEM-2895)
// ============================================================================

/**
 * Backend API response type for a single summary (snake_case).
 * @internal
 */
interface BackendSummaryResponse {
  id: number;
  content: string;
  event_count: number | null | undefined;
  window_start: string;
  window_end: string;
  generated_at: string;
  structured?: {
    bullet_points?: Array<{ icon: string; text: string; severity?: string | null }>;
    focus_areas?: string[];
    dominant_patterns?: string[];
    max_risk_score?: number | null;
    weather_conditions?: string[];
  } | null;
}

/**
 * Backend API response type for latest summaries (snake_case).
 * @internal
 */
interface BackendSummariesLatestResponse {
  hourly: BackendSummaryResponse | null;
  daily: BackendSummaryResponse | null;
}

/**
 * Format a time range from ISO timestamps to human-readable format.
 * @internal
 * @example
 * formatTimeRange('2026-01-18T14:00:00Z', '2026-01-18T15:00:00Z') => '2:00 PM - 3:00 PM'
 */
function formatTimeRange(startISO: string, endISO: string): string {
  try {
    const start = new Date(startISO);
    const end = new Date(endISO);

    // If times are invalid, return empty string
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return '';
    }

    // Format time as "h:mm AM/PM"
    const formatTime = (date: Date): string => {
      let hours = date.getHours();
      const minutes = date.getMinutes();
      const ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12;
      hours = hours || 12; // 0 becomes 12
      const minutesStr = minutes < 10 ? `0${minutes}` : `${minutes}`;
      return `${hours}:${minutesStr} ${ampm}`;
    };

    const startFormatted = formatTime(start);
    const endFormatted = formatTime(end);

    // If start and end are the same, return single time
    if (startFormatted === endFormatted) {
      return startFormatted;
    }

    return `${startFormatted} - ${endFormatted}`;
  } catch {
    return '';
  }
}

/**
 * Transform a backend summary response to frontend format (snake_case to camelCase).
 * @internal
 */
function transformSummaryResponse(
  backend: BackendSummaryResponse | null
): SummariesLatestResponse['hourly'] {
  if (!backend) return null;

  return {
    id: backend.id,
    content: backend.content,
    eventCount: backend.event_count ?? 0,
    windowStart: backend.window_start,
    windowEnd: backend.window_end,
    generatedAt: backend.generated_at,
    maxRiskScore: backend.structured?.max_risk_score ?? undefined,
    bulletPoints: backend.structured?.bullet_points?.map((bp) => ({
      icon: bp.icon as 'alert' | 'location' | 'pattern' | 'time' | 'weather',
      text: bp.text,
      severity: bp.severity ? parseInt(bp.severity, 10) || undefined : undefined,
    })),
    focusAreas: backend.structured?.focus_areas,
    dominantPatterns: backend.structured?.dominant_patterns,
    timeRangeFormatted: formatTimeRange(backend.window_start, backend.window_end),
    weatherConditions: backend.structured?.weather_conditions?.join(', '),
  };
}

/**
 * Fetch the latest hourly and daily summaries.
 *
 * Summaries are LLM-generated narrative descriptions of high/critical
 * security events. The hourly summary covers the past 60 minutes,
 * and the daily summary covers since midnight.
 *
 * @returns Latest summaries response with hourly and daily summaries
 *
 * @example
 * ```typescript
 * const { hourly, daily } = await fetchSummaries();
 * if (hourly) {
 *   console.log(`Hourly: ${hourly.content} (${hourly.eventCount} events)`);
 * }
 * ```
 */
export async function fetchSummaries(): Promise<SummariesLatestResponse> {
  const response = await fetchApi<BackendSummariesLatestResponse>('/api/summaries/latest');

  return {
    hourly: transformSummaryResponse(response.hourly),
    daily: transformSummaryResponse(response.daily),
  };
}

// ============================================================================
// Hierarchy Types (Organizational Structure - NEM-3137)
// ============================================================================

/**
 * Household organization unit.
 * Top-level container for members, vehicles, and properties.
 */
export interface Household {
  /** Unique household identifier */
  id: number;
  /** Household name (e.g., "Svoboda Family") */
  name: string;
  /** Timestamp when household was created */
  created_at: string;
}

/**
 * Request body for creating a new household.
 */
export interface HouseholdCreate {
  /** Household name (1-100 characters) */
  name: string;
}

/**
 * Request body for updating an existing household.
 */
export interface HouseholdUpdate {
  /** New household name (optional) */
  name?: string;
}

/**
 * Response for listing households.
 */
export interface HouseholdListResponse {
  /** List of households */
  items: Household[];
  /** Total number of households */
  total: number;
}

/**
 * Property represents a physical location within a household.
 */
export interface Property {
  /** Unique property identifier */
  id: number;
  /** ID of the owning household */
  household_id: number;
  /** Property name (e.g., "Main House") */
  name: string;
  /** Street address (optional) */
  address: string | null;
  /** Timezone in IANA format */
  timezone: string;
  /** Timestamp when property was created */
  created_at: string;
}

/**
 * Request body for creating a new property.
 */
export interface PropertyCreate {
  /** Property name (1-100 characters) */
  name: string;
  /** Street address (optional) */
  address?: string;
  /** Timezone (defaults to "UTC") */
  timezone?: string;
}

/**
 * Request body for updating an existing property.
 */
export interface PropertyUpdate {
  /** New property name (optional) */
  name?: string;
  /** New address (optional) */
  address?: string;
  /** New timezone (optional) */
  timezone?: string;
}

/**
 * Response for listing properties.
 */
export interface PropertyListResponse {
  /** List of properties */
  items: Property[];
  /** Total number of properties */
  total: number;
}

/**
 * Area represents a logical zone within a property.
 */
export interface Area {
  /** Unique area identifier */
  id: number;
  /** ID of the parent property */
  property_id: number;
  /** Area name (e.g., "Front Yard") */
  name: string;
  /** Description (optional) */
  description: string | null;
  /** Hex color code for UI display */
  color: string;
  /** Timestamp when area was created */
  created_at: string;
}

/**
 * Request body for creating a new area.
 */
export interface AreaCreate {
  /** Area name (1-100 characters) */
  name: string;
  /** Description (optional) */
  description?: string;
  /** Hex color code (defaults to "#76B900") */
  color?: string;
}

/**
 * Request body for updating an existing area.
 */
export interface AreaUpdate {
  /** New area name (optional) */
  name?: string;
  /** New description (optional) */
  description?: string;
  /** New color (optional) */
  color?: string;
}

/**
 * Response for listing areas.
 */
export interface AreaListResponse {
  /** List of areas */
  items: Area[];
  /** Total number of areas */
  total: number;
}

/**
 * Camera info in area context (minimal camera info).
 */
export interface AreaCamera {
  /** Camera ID */
  id: string;
  /** Camera name */
  name: string;
  /** Camera status */
  status: string;
}

/**
 * Response for listing cameras in an area.
 */
export interface AreaCamerasResponse {
  /** Area ID */
  area_id: number;
  /** Area name */
  area_name: string;
  /** List of cameras in this area */
  cameras: AreaCamera[];
  /** Number of cameras in this area */
  count: number;
}

/**
 * Request body for linking a camera to an area.
 */
export interface CameraLinkRequest {
  /** Camera ID to link */
  camera_id: string;
}

/**
 * Response for camera link/unlink operations.
 */
export interface CameraLinkResponse {
  /** Area ID */
  area_id: number;
  /** Camera ID */
  camera_id: string;
  /** Whether the camera is now linked (true) or unlinked (false) */
  linked: boolean;
}

// ============================================================================
// Hierarchy API Endpoints (NEM-3137)
// ============================================================================

// --- Household CRUD ---

/**
 * Fetch all households.
 *
 * @returns List of households
 */
export async function fetchHouseholds(): Promise<Household[]> {
  const response = await fetchApi<HouseholdListResponse>('/api/v1/households');
  return response.items;
}

/**
 * Fetch a single household by ID.
 *
 * @param id - Household ID
 * @returns Household object
 */
export async function fetchHousehold(id: number): Promise<Household> {
  return fetchApi<Household>(`/api/v1/households/${id}`);
}

/**
 * Create a new household.
 *
 * @param data - Household creation data
 * @returns Created household
 */
export async function createHousehold(data: HouseholdCreate): Promise<Household> {
  return fetchApi<Household>('/api/v1/households', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing household.
 *
 * @param id - Household ID
 * @param data - Update data
 * @returns Updated household
 */
export async function updateHousehold(id: number, data: HouseholdUpdate): Promise<Household> {
  return fetchApi<Household>(`/api/v1/households/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a household.
 *
 * @param id - Household ID
 */
export async function deleteHousehold(id: number): Promise<void> {
  return fetchApi<void>(`/api/v1/households/${id}`, {
    method: 'DELETE',
  });
}

// --- Property CRUD ---

/**
 * Fetch all properties for a household.
 *
 * @param householdId - Household ID
 * @returns List of properties
 */
export async function fetchProperties(householdId: number): Promise<Property[]> {
  const response = await fetchApi<PropertyListResponse>(
    `/api/v1/households/${householdId}/properties`
  );
  return response.items;
}

/**
 * Fetch a single property by ID.
 *
 * @param id - Property ID
 * @returns Property object
 */
export async function fetchProperty(id: number): Promise<Property> {
  return fetchApi<Property>(`/api/v1/properties/${id}`);
}

/**
 * Create a new property under a household.
 *
 * @param householdId - Household ID
 * @param data - Property creation data
 * @returns Created property
 */
export async function createProperty(householdId: number, data: PropertyCreate): Promise<Property> {
  return fetchApi<Property>(`/api/v1/households/${householdId}/properties`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing property.
 *
 * @param id - Property ID
 * @param data - Update data
 * @returns Updated property
 */
export async function updateProperty(id: number, data: PropertyUpdate): Promise<Property> {
  return fetchApi<Property>(`/api/v1/properties/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a property.
 *
 * @param id - Property ID
 */
export async function deleteProperty(id: number): Promise<void> {
  return fetchApi<void>(`/api/v1/properties/${id}`, {
    method: 'DELETE',
  });
}

// --- Area CRUD ---

/**
 * Fetch all areas for a property.
 *
 * @param propertyId - Property ID
 * @returns List of areas
 */
export async function fetchAreas(propertyId: number): Promise<Area[]> {
  const response = await fetchApi<AreaListResponse>(`/api/v1/properties/${propertyId}/areas`);
  return response.items;
}

/**
 * Fetch a single area by ID.
 *
 * @param id - Area ID
 * @returns Area object
 */
export async function fetchArea(id: number): Promise<Area> {
  return fetchApi<Area>(`/api/v1/areas/${id}`);
}

/**
 * Create a new area under a property.
 *
 * @param propertyId - Property ID
 * @param data - Area creation data
 * @returns Created area
 */
export async function createArea(propertyId: number, data: AreaCreate): Promise<Area> {
  return fetchApi<Area>(`/api/v1/properties/${propertyId}/areas`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing area.
 *
 * @param id - Area ID
 * @param data - Update data
 * @returns Updated area
 */
export async function updateArea(id: number, data: AreaUpdate): Promise<Area> {
  return fetchApi<Area>(`/api/v1/areas/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Delete an area.
 *
 * @param id - Area ID
 */
export async function deleteArea(id: number): Promise<void> {
  return fetchApi<void>(`/api/v1/areas/${id}`, {
    method: 'DELETE',
  });
}

// --- Camera Linking ---

/**
 * Fetch all cameras linked to an area.
 *
 * @param areaId - Area ID
 * @returns Area cameras response with list of cameras
 */
export async function fetchAreaCameras(areaId: number): Promise<AreaCamerasResponse> {
  return fetchApi<AreaCamerasResponse>(`/api/v1/areas/${areaId}/cameras`);
}

/**
 * Link a camera to an area.
 *
 * @param areaId - Area ID
 * @param cameraId - Camera ID to link
 * @returns Link response
 */
export async function linkCameraToArea(
  areaId: number,
  cameraId: string
): Promise<CameraLinkResponse> {
  return fetchApi<CameraLinkResponse>(`/api/v1/areas/${areaId}/cameras`, {
    method: 'POST',
    body: JSON.stringify({ camera_id: cameraId }),
  });
}

/**
 * Unlink a camera from an area.
 *
 * @param areaId - Area ID
 * @param cameraId - Camera ID to unlink
 * @returns Unlink response
 */
export async function unlinkCameraFromArea(
  areaId: number,
  cameraId: string
): Promise<CameraLinkResponse> {
  return fetchApi<CameraLinkResponse>(`/api/v1/areas/${areaId}/cameras/${cameraId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Memory Debug Endpoints (NEM-3173)
// ============================================================================

/**
 * Garbage collector statistics.
 */
export interface MemoryGCStats {
  /** Number of collections per generation */
  collections: number[];
  /** Total objects collected */
  collected: number;
  /** Number of uncollectable objects */
  uncollectable: number;
  /** Collection thresholds per generation */
  thresholds: number[];
}

/**
 * Statistics for a single object type.
 */
export interface MemoryObjectStats {
  /** Object type name (e.g., 'dict', 'list', 'str') */
  type_name: string;
  /** Number of instances */
  count: number;
  /** Total size in bytes */
  size_bytes: number;
  /** Human-readable size */
  size_human: string;
}

/**
 * Top memory allocation entry from tracemalloc.
 */
export interface TraceMallocAllocation {
  /** File path and line number */
  file: string;
  /** Size in bytes */
  size_bytes: number;
  /** Human-readable size */
  size_human: string;
  /** Number of allocations */
  count: number;
}

/**
 * Tracemalloc statistics.
 */
export interface TraceMallocStats {
  /** Whether tracemalloc is enabled */
  enabled: boolean;
  /** Current traced memory in bytes */
  current_bytes: number;
  /** Peak traced memory in bytes */
  peak_bytes: number;
  /** Top memory allocations by size */
  top_allocations: TraceMallocAllocation[];
}

/**
 * Response from GET /api/debug/memory
 */
export interface MemoryStatsResponse {
  /** Process RSS memory in bytes */
  process_rss_bytes: number;
  /** Human-readable RSS memory */
  process_rss_human: string;
  /** Process virtual memory in bytes */
  process_vms_bytes: number;
  /** Human-readable virtual memory */
  process_vms_human: string;
  /** Garbage collector statistics */
  gc_stats: MemoryGCStats;
  /** Tracemalloc statistics */
  tracemalloc_stats: TraceMallocStats;
  /** Top object types by memory usage */
  top_objects: MemoryObjectStats[];
  /** ISO timestamp of response */
  timestamp: string;
}

/**
 * Response from POST /api/debug/memory/gc
 */
export interface TriggerGcResponse {
  /** Objects collected per generation */
  collected: {
    gen0: number;
    gen1: number;
    gen2: number;
    total: number;
  };
  /** Memory before and after GC */
  memory: {
    rss_before_bytes: number;
    rss_after_bytes: number;
    freed_bytes: number;
    freed_human: string;
  };
  /** Number of uncollectable objects */
  uncollectable: number;
  /** ISO timestamp */
  timestamp: string;
}

/**
 * Response from POST /api/debug/memory/tracemalloc/start
 */
export interface StartTracemallocResponse {
  /** Operation status */
  status: 'started' | 'already_running';
  /** Number of frames if started */
  nframes?: number;
  /** Human-readable message */
  message: string;
  /** ISO timestamp */
  timestamp: string;
}

/**
 * Response from POST /api/debug/memory/tracemalloc/stop
 */
export interface StopTracemallocResponse {
  /** Operation status */
  status: 'stopped' | 'not_running';
  /** Final memory stats before stopping */
  final_stats?: {
    current_bytes: number;
    current_human: string;
    peak_bytes: number;
    peak_human: string;
  };
  /** Human-readable message */
  message: string;
  /** ISO timestamp */
  timestamp: string;
}

/**
 * Fetch memory statistics from the debug API.
 *
 * Returns detailed memory usage including process RSS/VMS, GC stats,
 * tracemalloc data, and top objects by memory consumption.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @param options - Query options
 * @param options.topN - Number of top objects to return (default: 20)
 * @param options.forceGc - Force GC before measurement (default: false)
 * @returns Memory statistics response
 *
 * @example
 * ```typescript
 * const stats = await fetchMemoryStats();
 * console.log(`RSS: ${stats.process_rss_human}`);
 * console.log(`Top object: ${stats.top_objects[0].type_name}`);
 * ```
 */
export async function fetchMemoryStats(options?: {
  topN?: number;
  forceGc?: boolean;
}): Promise<MemoryStatsResponse> {
  const params = new URLSearchParams();
  if (options?.topN !== undefined) {
    params.set('top_n', options.topN.toString());
  }
  if (options?.forceGc !== undefined) {
    params.set('force_gc', options.forceGc.toString());
  }
  const query = params.toString();
  const url = query ? `/api/debug/memory?${query}` : '/api/debug/memory';
  return fetchApi<MemoryStatsResponse>(url);
}

/**
 * Trigger garbage collection and return statistics.
 *
 * Forces a full GC cycle across all generations and returns
 * the number of objects collected and memory freed.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @returns GC trigger response with collection stats
 *
 * @example
 * ```typescript
 * const result = await triggerGc();
 * console.log(`Collected ${result.collected.total} objects`);
 * console.log(`Freed ${result.memory.freed_human}`);
 * ```
 */
export async function triggerGc(): Promise<TriggerGcResponse> {
  return fetchApi<TriggerGcResponse>('/api/debug/memory/gc', {
    method: 'POST',
  });
}

/**
 * Start tracemalloc memory tracing.
 *
 * Enables detailed memory allocation tracking. Adds some overhead
 * but allows tracking where memory is being allocated.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @param nframes - Number of stack frames to capture (default: 25)
 * @returns Start tracemalloc response
 *
 * @example
 * ```typescript
 * const result = await startTracemalloc(10);
 * console.log(result.message); // "tracemalloc started with 10 frames"
 * ```
 */
export async function startTracemalloc(nframes?: number): Promise<StartTracemallocResponse> {
  const params = nframes !== undefined ? `?nframes=${nframes}` : '';
  return fetchApi<StartTracemallocResponse>(`/api/debug/memory/tracemalloc/start${params}`, {
    method: 'POST',
  });
}

/**
 * Stop tracemalloc memory tracing.
 *
 * Stops memory allocation tracking and returns final statistics.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @returns Stop tracemalloc response with final stats
 *
 * @example
 * ```typescript
 * const result = await stopTracemalloc();
 * if (result.final_stats) {
 *   console.log(`Peak memory: ${result.final_stats.peak_human}`);
 * }
 * ```
 */
export async function stopTracemalloc(): Promise<StopTracemallocResponse> {
  return fetchApi<StopTracemallocResponse>('/api/debug/memory/tracemalloc/stop', {
    method: 'POST',
  });
}

/**
 * Response from GET /api/debug/circuit-breakers
 */
export interface DebugCircuitBreakersResponse {
  /** All circuit breaker states keyed by name */
  circuit_breakers: Record<
    string,
    {
      name: string;
      state: 'closed' | 'open' | 'half_open';
      failure_count: number;
      success_count: number;
      last_failure_time: number | null;
      config: {
        failure_threshold: number;
        recovery_timeout: number;
        half_open_max_calls: number;
      };
    }
  >;
  /** ISO timestamp of response */
  timestamp: string;
}

/**
 * Fetch circuit breaker states from the debug API.
 *
 * Returns detailed circuit breaker information including states,
 * failure counts, and configuration for all registered breakers.
 *
 * Only available when debug mode is enabled on the backend.
 *
 * @returns Debug circuit breakers response
 *
 * @example
 * ```typescript
 * const result = await fetchDebugCircuitBreakers();
 * for (const [name, breaker] of Object.entries(result.circuit_breakers)) {
 *   console.log(`${name}: ${breaker.state} (${breaker.failure_count} failures)`);
 * }
 * ```
 */
export async function fetchDebugCircuitBreakers(): Promise<DebugCircuitBreakersResponse> {
  return fetchApi<DebugCircuitBreakersResponse>('/api/debug/circuit-breakers');
}

// ============================================================================
// System Logs API (NEM-3272)
// ============================================================================

/**
 * Log statistics response from /api/logs/stats.
 * Uses optimized UNION ALL query for efficient aggregation.
 */
export interface LogStats {
  /** Number of ERROR logs today */
  errors_today: number;
  /** Number of WARNING logs today */
  warnings_today: number;
  /** Total number of logs today */
  total_today: number;
  /** Component with the most logs today (if any) */
  top_component?: string | null;
  /** Breakdown of log counts by component */
  by_component?: Record<string, number>;
}

/**
 * Query parameters for fetching logs with pagination and filtering.
 */
export interface LogsQueryParams {
  /** Filter by log level (ERROR, WARNING, INFO, DEBUG) */
  level?: string;
  /** Filter by component name */
  component?: string;
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter by source */
  source?: string;
  /** Full-text search in log messages */
  search?: string;
  /** Start date for time range filter (ISO 8601) */
  start_date?: string;
  /** End date for time range filter (ISO 8601) */
  end_date?: string;
  /** Maximum number of logs to return (default: 100, max: 1000) */
  limit?: number;
  /** Cursor for pagination (from previous response) */
  cursor?: string;
  /** Include total count in response (slower query) */
  include_total_count?: boolean;
}

/**
 * Individual log entry from the system.
 */
export interface LogEntry {
  /** Unique log ID */
  id: number;
  /** ISO 8601 timestamp */
  timestamp: string;
  /** Log level (ERROR, WARNING, INFO, DEBUG) */
  level: string;
  /** Component that generated the log */
  component: string;
  /** Log message content */
  message: string;
  /** Associated camera ID (if any) */
  camera_id?: string | null;
  /** Associated event ID (if any) */
  event_id?: number | null;
  /** Request ID for tracing */
  request_id?: string | null;
  /** Associated detection ID (if any) */
  detection_id?: number | null;
  /** Operation duration in milliseconds (if applicable) */
  duration_ms?: number | null;
  /** Additional structured data */
  extra?: Record<string, unknown> | null;
  /** Log source identifier */
  source: string;
}

/**
 * Paginated response for logs list endpoint.
 */
export interface LogsListResponse {
  /** Array of log entries */
  items: LogEntry[];
  /** Pagination metadata */
  pagination: {
    /** Total count (only if include_total_count=true) */
    total: number;
    /** Maximum items per page */
    limit: number;
    /** Current offset (deprecated, use cursor) */
    offset?: number;
    /** Current cursor position */
    cursor?: string | null;
    /** Cursor for next page (null if no more results) */
    next_cursor?: string | null;
    /** Whether more results are available */
    has_more: boolean;
  };
  /** Deprecation warning for offset-based pagination */
  deprecation_warning?: string | null;
}

/**
 * Fetch log statistics for the current day.
 *
 * Returns aggregated statistics including error counts, warning counts,
 * total logs, and breakdown by component. Uses an optimized UNION ALL
 * query on the backend for efficient single-pass aggregation.
 *
 * @returns Log statistics for today
 *
 * @example
 * ```typescript
 * const stats = await fetchLogStats();
 * console.log(`Errors today: ${stats.errors_today}`);
 * console.log(`Warnings today: ${stats.warnings_today}`);
 * console.log(`Total logs: ${stats.total_today}`);
 * ```
 */
export async function fetchLogStats(): Promise<LogStats> {
  return fetchApi<LogStats>('/api/logs/stats');
}

/**
 * Fetch logs with optional filtering and pagination.
 *
 * Supports filtering by level, component, camera, source, search text,
 * and time range. Uses cursor-based pagination for efficient traversal.
 *
 * @param params - Optional query parameters for filtering and pagination
 * @param options - Optional fetch options including AbortSignal
 * @returns Paginated list of log entries
 *
 * @example
 * ```typescript
 * // Fetch recent errors
 * const errors = await fetchLogs({ level: 'ERROR', limit: 50 });
 *
 * // Fetch logs for a specific camera
 * const cameraLogs = await fetchLogs({
 *   camera_id: 'cam-1',
 *   start_date: '2024-01-01T00:00:00Z',
 *   limit: 100
 * });
 *
 * // Paginate through results
 * let response = await fetchLogs({ limit: 100 });
 * while (response.pagination.has_more) {
 *   response = await fetchLogs({
 *     limit: 100,
 *     cursor: response.pagination.next_cursor
 *   });
 * }
 * ```
 */
export async function fetchLogs(
  params?: LogsQueryParams,
  options?: FetchOptions
): Promise<LogsListResponse> {
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
    if (params.cursor) queryParams.append('cursor', params.cursor);
    if (params.include_total_count) queryParams.append('include_total_count', 'true');
  }
  const queryString = queryParams.toString();
  const endpoint = queryString ? `/api/logs?${queryString}` : '/api/logs';
  return fetchApi<LogsListResponse>(endpoint, options);
}
