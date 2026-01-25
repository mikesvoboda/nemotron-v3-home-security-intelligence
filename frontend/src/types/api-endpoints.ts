/**
 * API Endpoint Template Literal Types
 *
 * This module provides type-safe API endpoint definitions using TypeScript
 * template literal types. It enables:
 *
 * 1. Compile-time validation of endpoint strings
 * 2. Automatic response type inference based on endpoint patterns
 * 3. Type-safe API client methods with correct return types
 * 4. Runtime endpoint validation and parsing
 *
 * @example
 * ```ts
 * // Type-safe endpoint building
 * const endpoint = cameraEndpoint('abc-123'); // '/api/cameras/abc-123'
 *
 * // Automatic response type inference
 * const camera = await apiGet('/api/cameras/abc-123'); // Type: Camera
 * const cameras = await apiGet('/api/cameras'); // Type: Camera[]
 * ```
 *
 * @see NEM-1556
 */

import type {
  Camera,
  CameraListResponse,
  Event,
  EventListResponse,
  EventStatsResponse,
  HealthResponse,
  ReadinessResponse,
  GPUStats,
  GPUStatsHistoryResponse,
  SystemConfig,
  SystemStats,
  TelemetryResponse,
  DetectionListResponse,
  AlertRule,
  AlertRuleListResponse,
  Zone,
  ZoneListResponse,
  AuditLogResponse,
  AuditLogListResponse,
  AuditLogStats,
  SearchResponse,
  CircuitBreakersResponse,
  SeverityMetadataResponse,
  PipelineLatencyResponse,
  PipelineLatencyHistoryResponse,
  SceneChangeListResponse,
} from './generated';

// ============================================================================
// Base ID Types for Template Literals
// ============================================================================

/**
 * Template literal type for string IDs (UUIDs, slugs, etc.)
 * Matches any non-empty string that doesn't contain '/'
 */
type StringId = string;

/**
 * Template literal type for numeric IDs
 * At compile-time this is string, validated at runtime
 */
type NumericId = string;

// ============================================================================
// Camera Endpoints
// ============================================================================

/**
 * Camera API endpoints
 *
 * - `/api/cameras` - List all cameras
 * - `/api/cameras/:id` - Get camera by ID
 * - `/api/cameras/:id/snapshot` - Get camera snapshot
 * - `/api/cameras/:id/zones` - List camera zones
 * - `/api/cameras/:id/zones/:zoneId` - Get specific zone
 * - `/api/cameras/:id/baseline/activity` - Get activity baseline
 * - `/api/cameras/:id/baseline/classes` - Get class baseline
 */
export type CameraEndpoint =
  | '/api/cameras'
  | `/api/cameras/${StringId}`
  | `/api/cameras/${StringId}/snapshot`
  | `/api/cameras/${StringId}/zones`
  | `/api/cameras/${StringId}/zones/${StringId}`
  | `/api/cameras/${StringId}/baseline/activity`
  | `/api/cameras/${StringId}/baseline/classes`;

// ============================================================================
// Event Endpoints
// ============================================================================

/**
 * Event API endpoints
 *
 * - `/api/events` - List events
 * - `/api/events/:id` - Get event by ID
 * - `/api/events/stats` - Get event statistics
 * - `/api/events/search` - Search events
 * - `/api/events/export` - Export events
 * - `/api/events/:id/detections` - List event detections
 */
export type EventEndpoint =
  | '/api/events'
  | `/api/events/${NumericId}`
  | '/api/events/stats'
  | '/api/events/search'
  | '/api/events/export'
  | `/api/events/${NumericId}/detections`;

// ============================================================================
// System Endpoints
// ============================================================================

/**
 * System API endpoints
 *
 * - `/api/system/health` - Health check
 * - `/api/system/health/ready` - Readiness check
 * - `/api/system/gpu` - GPU statistics
 * - `/api/system/gpu/history` - GPU history
 * - `/api/system/config` - System configuration
 * - `/api/system/stats` - System statistics
 * - `/api/system/storage` - Storage statistics
 * - `/api/system/telemetry` - Telemetry data
 * - `/api/system/models` - Model zoo status
 * - `/api/system/severity` - Severity metadata
 * - `/api/system/cleanup` - Cleanup endpoint
 * - `/api/system/circuit-breakers` - Circuit breakers
 * - `/api/system/circuit-breakers/:name/reset` - Reset circuit breaker
 * - `/api/system/pipeline-latency` - Pipeline latency
 * - `/api/system/pipeline-latency/history` - Pipeline latency history
 * - `/api/system/anomaly-config` - Anomaly configuration
 * - `/api/system/services/:name/restart` - Restart service
 */
export type SystemEndpoint =
  | '/api/system/health'
  | '/api/system/health/ready'
  | '/api/system/gpu'
  | '/api/system/gpu/history'
  | '/api/system/config'
  | '/api/system/stats'
  | '/api/system/storage'
  | '/api/system/telemetry'
  | '/api/system/models'
  | '/api/system/severity'
  | '/api/system/cleanup'
  | '/api/system/circuit-breakers'
  | `/api/system/circuit-breakers/${StringId}/reset`
  | '/api/system/pipeline-latency'
  | '/api/system/pipeline-latency/history'
  | '/api/system/anomaly-config'
  | `/api/system/services/${StringId}/restart`;

// ============================================================================
// Detection Endpoints
// ============================================================================

/**
 * Detection API endpoints
 *
 * - `/api/detections/stats` - Detection statistics
 * - `/api/detections/:id/image` - Detection image
 * - `/api/detections/:id/video` - Detection video
 * - `/api/detections/:id/video/thumbnail` - Detection video thumbnail
 */
export type DetectionEndpoint =
  | '/api/detections/stats'
  | `/api/detections/${NumericId}/image`
  | `/api/detections/${NumericId}/video`
  | `/api/detections/${NumericId}/video/thumbnail`;

// ============================================================================
// Enrichment Endpoints
// ============================================================================

/**
 * Enrichment API endpoints
 *
 * - `/api/detections/:id/enrichment` - Get enrichment for detection
 */
export type EnrichmentEndpoint = `/api/detections/${NumericId}/enrichment`;

// ============================================================================
// Alert Rule Endpoints
// ============================================================================

/**
 * Alert Rule API endpoints
 *
 * - `/api/alerts/rules` - List alert rules
 * - `/api/alerts/rules/:id` - Get alert rule
 * - `/api/alerts/rules/:id/test` - Test alert rule
 */
export type AlertRuleEndpoint =
  | '/api/alerts/rules'
  | `/api/alerts/rules/${StringId}`
  | `/api/alerts/rules/${StringId}/test`;

// ============================================================================
// Zone Endpoints
// ============================================================================

/**
 * Zone API endpoints (nested under cameras)
 *
 * - `/api/cameras/:cameraId/zones` - List zones
 * - `/api/cameras/:cameraId/zones/:zoneId` - Get zone
 */
export type ZoneEndpoint =
  | `/api/cameras/${StringId}/zones`
  | `/api/cameras/${StringId}/zones/${StringId}`;

// ============================================================================
// Audit Endpoints
// ============================================================================

/**
 * Audit Log API endpoints
 *
 * - `/api/audit` - List audit logs
 * - `/api/audit/:id` - Get audit log
 * - `/api/audit/stats` - Audit statistics
 */
export type AuditEndpoint = '/api/audit' | `/api/audit/${NumericId}` | '/api/audit/stats';

// ============================================================================
// Search Endpoints
// ============================================================================

/**
 * Search API endpoints
 *
 * - `/api/events/search` - Search events
 */
export type SearchEndpoint = '/api/events/search';

// ============================================================================
// DLQ Endpoints
// ============================================================================

/**
 * Dead Letter Queue API endpoints
 */
export type DLQEndpoint =
  | '/api/dlq/stats'
  | `/api/dlq/jobs/${StringId}`
  | `/api/dlq/requeue/${StringId}`
  | `/api/dlq/requeue-all/${StringId}`
  | `/api/dlq/${StringId}`;

// ============================================================================
// Notification Endpoints
// ============================================================================

/**
 * Notification API endpoints
 */
export type NotificationEndpoint = '/api/notification/config' | '/api/notification/test';

// ============================================================================
// AI Audit Endpoints
// ============================================================================

/**
 * AI Audit API endpoints
 */
export type AiAuditEndpoint =
  | '/api/ai-audit/stats'
  | '/api/ai-audit/leaderboard'
  | '/api/ai-audit/recommendations'
  | `/api/ai-audit/events/${NumericId}`;

// ============================================================================
// Media Endpoints
// ============================================================================

/**
 * Media API endpoints
 */
export type MediaEndpoint =
  | `/api/media/cameras/${StringId}/${StringId}`
  | `/api/media/thumbnails/${StringId}`;

// ============================================================================
// Scene Change Endpoints
// ============================================================================

/**
 * Scene Change API endpoints
 */
export type SceneChangeEndpoint =
  | '/api/scene-changes'
  | `/api/scene-changes/${NumericId}`
  | `/api/scene-changes/${NumericId}/acknowledge`;

// ============================================================================
// Union of All API Endpoints
// ============================================================================

/**
 * Union type of all valid API endpoints.
 * Use this type to validate endpoint strings at compile time.
 */
export type ApiEndpoint =
  | CameraEndpoint
  | EventEndpoint
  | SystemEndpoint
  | DetectionEndpoint
  | EnrichmentEndpoint
  | AlertRuleEndpoint
  | ZoneEndpoint
  | AuditEndpoint
  | SearchEndpoint
  | DLQEndpoint
  | NotificationEndpoint
  | AiAuditEndpoint
  | MediaEndpoint
  | SceneChangeEndpoint;

// ============================================================================
// Response Type Mapping
// ============================================================================

// NOTE: We use EndpointResponseType<T> (conditional type) for response type inference
// instead of an index signature map, which has issues with overlapping template literal patterns.
// See EndpointResponseType below for the actual type mapping implementation.

/**
 * Enrichment response type (local definition until added to generated types)
 */
interface EnrichmentResponse {
  detection_id: number;
  enriched_at: string | null;
  license_plate?: unknown;
  face?: unknown;
  vehicle?: unknown;
  clothing?: unknown;
  violence?: unknown;
  weather?: unknown;
  pose?: unknown;
  depth?: unknown;
  image_quality?: unknown;
  pet?: unknown;
}

/**
 * Detection stats response type (local definition until added to generated types)
 */
interface DetectionStatsResponse {
  total_detections: number;
  detections_by_class: Record<string, number>;
  average_confidence: number | null;
}

// ============================================================================
// Response Type Inference
// ============================================================================

/**
 * Infers the response type for a given API endpoint.
 *
 * Uses conditional types to match endpoint patterns and return
 * the appropriate response type.
 *
 * @example
 * ```ts
 * type CamerasResponse = EndpointResponseType<'/api/cameras'>; // CameraListResponse
 * type CameraResponse = EndpointResponseType<'/api/cameras/abc'>; // Camera
 * type EventResponse = EndpointResponseType<'/api/events/123'>; // Event
 * ```
 */
export type EndpointResponseType<T extends string> =
  // Exact matches first (most specific)
  T extends '/api/cameras'
    ? CameraListResponse
    : T extends '/api/events'
      ? EventListResponse
      : T extends '/api/events/stats'
        ? EventStatsResponse
        : T extends '/api/events/search'
          ? SearchResponse
          : T extends '/api/system/health'
            ? HealthResponse
            : T extends '/api/system/health/ready'
              ? ReadinessResponse
              : T extends '/api/system/gpu'
                ? GPUStats
                : T extends '/api/system/gpu/history'
                  ? GPUStatsHistoryResponse
                  : T extends '/api/system/config'
                    ? SystemConfig
                    : T extends '/api/system/stats'
                      ? SystemStats
                      : T extends '/api/system/telemetry'
                        ? TelemetryResponse
                        : T extends '/api/system/severity'
                          ? SeverityMetadataResponse
                          : T extends '/api/system/circuit-breakers'
                            ? CircuitBreakersResponse
                            : T extends '/api/system/pipeline-latency'
                              ? PipelineLatencyResponse
                              : T extends '/api/system/pipeline-latency/history'
                                ? PipelineLatencyHistoryResponse
                                : T extends '/api/alerts/rules'
                                  ? AlertRuleListResponse
                                  : T extends '/api/audit'
                                    ? AuditLogListResponse
                                    : T extends '/api/audit/stats'
                                      ? AuditLogStats
                                      : T extends '/api/detections/stats'
                                        ? DetectionStatsResponse
                                        : T extends '/api/scene-changes'
                                          ? SceneChangeListResponse
                                          : // Pattern matches (less specific)
                                            T extends `/api/cameras/${infer _}/zones/${infer _}`
                                            ? Zone
                                            : T extends `/api/cameras/${infer _}/zones`
                                              ? ZoneListResponse
                                              : T extends `/api/cameras/${infer _}`
                                                ? Camera
                                                : T extends `/api/events/${infer _}/detections`
                                                  ? DetectionListResponse
                                                  : T extends `/api/events/${infer _}`
                                                    ? Event
                                                    : T extends `/api/alerts/rules/${infer _}`
                                                      ? AlertRule
                                                      : T extends `/api/audit/${infer _}`
                                                        ? AuditLogResponse
                                                        : T extends `/api/detections/${infer _}/enrichment`
                                                          ? EnrichmentResponse
                                                          : unknown;

// ============================================================================
// ID Extraction Types
// ============================================================================

/**
 * Extracts the ID from an endpoint pattern.
 *
 * @example
 * ```ts
 * type Id1 = ExtractIdFromEndpoint<'/api/cameras/abc-123'>; // 'abc-123'
 * type Id2 = ExtractIdFromEndpoint<'/api/events/456'>; // '456'
 * type Id3 = ExtractIdFromEndpoint<'/api/cameras'>; // never
 * ```
 */
export type ExtractIdFromEndpoint<T extends string> =
  T extends `/api/cameras/${infer Id}/zones/${infer _}`
    ? Id
    : T extends `/api/cameras/${infer Id}/zones`
      ? Id
      : T extends `/api/cameras/${infer Id}/snapshot`
        ? Id
        : T extends `/api/cameras/${infer Id}/baseline/${infer _}`
          ? Id
          : T extends `/api/cameras/${infer Id}`
            ? Id
            : T extends `/api/events/${infer Id}/detections`
              ? Id
              : T extends `/api/events/${infer Id}`
                ? Id
                : T extends `/api/detections/${infer Id}/image`
                  ? Id
                  : T extends `/api/detections/${infer Id}/video`
                    ? Id
                    : T extends `/api/alerts/rules/${infer Id}/test`
                      ? Id
                      : T extends `/api/alerts/rules/${infer Id}`
                        ? Id
                        : T extends `/api/audit/${infer Id}`
                          ? Id
                          : T extends `/api/detections/${infer Id}/enrichment`
                            ? Id
                            : never;

// ============================================================================
// Endpoint Validation
// ============================================================================

/**
 * Parsed endpoint structure for runtime validation
 */
export interface ParsedEndpoint {
  resource: string;
  action: string;
  id: string | undefined;
  subResource: string | undefined;
  subId: string | undefined;
}

/**
 * Regular expressions for endpoint validation
 */
const ENDPOINT_PATTERNS = {
  // Camera endpoints
  cameras: /^\/api\/cameras$/,
  cameraDetail: /^\/api\/cameras\/([^/]+)$/,
  cameraSnapshot: /^\/api\/cameras\/([^/]+)\/snapshot$/,
  cameraZones: /^\/api\/cameras\/([^/]+)\/zones$/,
  cameraZoneDetail: /^\/api\/cameras\/([^/]+)\/zones\/([^/]+)$/,
  cameraBaseline: /^\/api\/cameras\/([^/]+)\/baseline\/(activity|classes)$/,

  // Event endpoints
  events: /^\/api\/events$/,
  eventDetail: /^\/api\/events\/(\d+)$/,
  eventStats: /^\/api\/events\/stats$/,
  eventSearch: /^\/api\/events\/search$/,
  eventExport: /^\/api\/events\/export$/,
  eventDetections: /^\/api\/events\/(\d+)\/detections$/,

  // System endpoints
  systemHealth: /^\/api\/system\/health$/,
  systemReady: /^\/api\/system\/health\/ready$/,
  systemGpu: /^\/api\/system\/gpu$/,
  systemGpuHistory: /^\/api\/system\/gpu\/history$/,
  systemConfig: /^\/api\/system\/config$/,
  systemStats: /^\/api\/system\/stats$/,
  systemStorage: /^\/api\/system\/storage$/,
  systemTelemetry: /^\/api\/system\/telemetry$/,
  systemModels: /^\/api\/system\/models$/,
  systemSeverity: /^\/api\/system\/severity$/,
  systemCleanup: /^\/api\/system\/cleanup$/,
  systemCircuitBreakers: /^\/api\/system\/circuit-breakers$/,
  systemCircuitBreakerReset: /^\/api\/system\/circuit-breakers\/([^/]+)\/reset$/,
  systemPipelineLatency: /^\/api\/system\/pipeline-latency$/,
  systemPipelineLatencyHistory: /^\/api\/system\/pipeline-latency\/history$/,
  systemAnomalyConfig: /^\/api\/system\/anomaly-config$/,
  systemServiceRestart: /^\/api\/system\/services\/([^/]+)\/restart$/,

  // Detection endpoints
  detectionStats: /^\/api\/detections\/stats$/,
  detectionImage: /^\/api\/detections\/(\d+)\/image$/,
  detectionVideo: /^\/api\/detections\/(\d+)\/video$/,
  detectionVideoThumbnail: /^\/api\/detections\/(\d+)\/video\/thumbnail$/,

  // Enrichment endpoints
  enrichment: /^\/api\/detections\/(\d+)\/enrichment$/,

  // Alert rule endpoints
  alertRules: /^\/api\/alerts\/rules$/,
  alertRuleDetail: /^\/api\/alerts\/rules\/([^/]+)$/,
  alertRuleTest: /^\/api\/alerts\/rules\/([^/]+)\/test$/,

  // Audit endpoints
  audit: /^\/api\/audit$/,
  auditDetail: /^\/api\/audit\/(\d+)$/,
  auditStats: /^\/api\/audit\/stats$/,

  // DLQ endpoints
  dlqStats: /^\/api\/dlq\/stats$/,
  dlqJobs: /^\/api\/dlq\/jobs\/([^/]+)$/,
  dlqRequeue: /^\/api\/dlq\/requeue\/([^/]+)$/,
  dlqRequeueAll: /^\/api\/dlq\/requeue-all\/([^/]+)$/,
  dlqClear: /^\/api\/dlq\/([^/]+)$/,

  // Notification endpoints
  notificationConfig: /^\/api\/notification\/config$/,
  notificationTest: /^\/api\/notification\/test$/,

  // AI Audit endpoints
  aiAuditStats: /^\/api\/ai-audit\/stats$/,
  aiAuditLeaderboard: /^\/api\/ai-audit\/leaderboard$/,
  aiAuditRecommendations: /^\/api\/ai-audit\/recommendations$/,
  aiAuditEvent: /^\/api\/ai-audit\/events\/(\d+)$/,

  // Scene change endpoints
  sceneChanges: /^\/api\/scene-changes$/,
  sceneChangeDetail: /^\/api\/scene-changes\/(\d+)$/,
  sceneChangeAcknowledge: /^\/api\/scene-changes\/(\d+)\/acknowledge$/,
};

/**
 * Validates if a string is a valid API endpoint.
 *
 * @param endpoint - The endpoint string to validate
 * @returns true if the endpoint matches a known pattern
 *
 * @example
 * ```ts
 * isValidEndpoint('/api/cameras'); // true
 * isValidEndpoint('/api/invalid'); // false
 * ```
 */
export function isValidEndpoint(endpoint: string): endpoint is ApiEndpoint {
  if (!endpoint || !endpoint.startsWith('/api/')) {
    return false;
  }

  return Object.values(ENDPOINT_PATTERNS).some((pattern) => pattern.test(endpoint));
}

/**
 * Parses an endpoint string into its component parts.
 *
 * @param endpoint - The endpoint string to parse
 * @returns ParsedEndpoint object or null if invalid
 *
 * @example
 * ```ts
 * parseEndpoint('/api/cameras/abc-123');
 * // { resource: 'cameras', action: 'detail', id: 'abc-123', subResource: undefined, subId: undefined }
 *
 * parseEndpoint('/api/cameras/abc-123/zones/zone-456');
 * // { resource: 'cameras', action: 'subdetail', id: 'abc-123', subResource: 'zones', subId: 'zone-456' }
 * ```
 */
export function parseEndpoint(endpoint: string): ParsedEndpoint | null {
  if (!endpoint || !endpoint.startsWith('/api/')) {
    return null;
  }

  // Camera endpoints
  if (ENDPOINT_PATTERNS.cameras.test(endpoint)) {
    return {
      resource: 'cameras',
      action: 'list',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  let match = endpoint.match(ENDPOINT_PATTERNS.cameraZoneDetail);
  if (match) {
    return {
      resource: 'cameras',
      action: 'subdetail',
      id: match[1],
      subResource: 'zones',
      subId: match[2],
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.cameraZones);
  if (match) {
    return {
      resource: 'cameras',
      action: 'sublist',
      id: match[1],
      subResource: 'zones',
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.cameraSnapshot);
  if (match) {
    return {
      resource: 'cameras',
      action: 'snapshot',
      id: match[1],
      subResource: undefined,
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.cameraBaseline);
  if (match) {
    return {
      resource: 'cameras',
      action: 'baseline',
      id: match[1],
      subResource: match[2],
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.cameraDetail);
  if (match) {
    return {
      resource: 'cameras',
      action: 'detail',
      id: match[1],
      subResource: undefined,
      subId: undefined,
    };
  }

  // Event endpoints
  if (ENDPOINT_PATTERNS.events.test(endpoint)) {
    return {
      resource: 'events',
      action: 'list',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.eventStats.test(endpoint)) {
    return {
      resource: 'events',
      action: 'stats',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.eventSearch.test(endpoint)) {
    return {
      resource: 'events',
      action: 'search',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.eventExport.test(endpoint)) {
    return {
      resource: 'events',
      action: 'export',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.eventDetections);
  if (match) {
    return {
      resource: 'events',
      action: 'sublist',
      id: match[1],
      subResource: 'detections',
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.eventDetail);
  if (match) {
    return {
      resource: 'events',
      action: 'detail',
      id: match[1],
      subResource: undefined,
      subId: undefined,
    };
  }

  // System endpoints
  if (ENDPOINT_PATTERNS.systemHealth.test(endpoint)) {
    return {
      resource: 'system',
      action: 'health',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemReady.test(endpoint)) {
    return {
      resource: 'system',
      action: 'ready',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemGpu.test(endpoint)) {
    return {
      resource: 'system',
      action: 'gpu',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemGpuHistory.test(endpoint)) {
    return {
      resource: 'system',
      action: 'gpu-history',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemConfig.test(endpoint)) {
    return {
      resource: 'system',
      action: 'config',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemStats.test(endpoint)) {
    return {
      resource: 'system',
      action: 'stats',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemStorage.test(endpoint)) {
    return {
      resource: 'system',
      action: 'storage',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemTelemetry.test(endpoint)) {
    return {
      resource: 'system',
      action: 'telemetry',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemModels.test(endpoint)) {
    return {
      resource: 'system',
      action: 'models',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemSeverity.test(endpoint)) {
    return {
      resource: 'system',
      action: 'severity',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemCleanup.test(endpoint)) {
    return {
      resource: 'system',
      action: 'cleanup',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemCircuitBreakers.test(endpoint)) {
    return {
      resource: 'system',
      action: 'circuit-breakers',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemPipelineLatency.test(endpoint)) {
    return {
      resource: 'system',
      action: 'pipeline-latency',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.systemPipelineLatencyHistory.test(endpoint)) {
    return {
      resource: 'system',
      action: 'pipeline-latency-history',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  // Detection endpoints
  if (ENDPOINT_PATTERNS.detectionStats.test(endpoint)) {
    return {
      resource: 'detections',
      action: 'stats',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.detectionImage);
  if (match) {
    return {
      resource: 'detections',
      action: 'image',
      id: match[1],
      subResource: undefined,
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.detectionVideo);
  if (match) {
    return {
      resource: 'detections',
      action: 'video',
      id: match[1],
      subResource: undefined,
      subId: undefined,
    };
  }

  // Enrichment endpoints (nested under detections)
  match = endpoint.match(ENDPOINT_PATTERNS.enrichment);
  if (match) {
    return {
      resource: 'detections',
      action: 'enrichment',
      id: match[1],
      subResource: undefined,
      subId: undefined,
    };
  }

  // Alert rule endpoints
  if (ENDPOINT_PATTERNS.alertRules.test(endpoint)) {
    return {
      resource: 'alerts',
      action: 'list',
      id: undefined,
      subResource: 'rules',
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.alertRuleTest);
  if (match) {
    return {
      resource: 'alerts',
      action: 'test',
      id: match[1],
      subResource: 'rules',
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.alertRuleDetail);
  if (match) {
    return {
      resource: 'alerts',
      action: 'detail',
      id: match[1],
      subResource: 'rules',
      subId: undefined,
    };
  }

  // Audit endpoints
  if (ENDPOINT_PATTERNS.audit.test(endpoint)) {
    return {
      resource: 'audit',
      action: 'list',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  if (ENDPOINT_PATTERNS.auditStats.test(endpoint)) {
    return {
      resource: 'audit',
      action: 'stats',
      id: undefined,
      subResource: undefined,
      subId: undefined,
    };
  }

  match = endpoint.match(ENDPOINT_PATTERNS.auditDetail);
  if (match) {
    return {
      resource: 'audit',
      action: 'detail',
      id: match[1],
      subResource: undefined,
      subId: undefined,
    };
  }

  return null;
}

// ============================================================================
// Endpoint Builders
// ============================================================================

/**
 * Builds camera API endpoints with type safety.
 *
 * @param id - Optional camera ID
 * @param action - Optional action (snapshot, zones, baseline/activity, baseline/classes)
 * @returns Type-safe endpoint string
 *
 * @example
 * ```ts
 * cameraEndpoint(); // '/api/cameras'
 * cameraEndpoint('abc-123'); // '/api/cameras/abc-123'
 * cameraEndpoint('abc-123', 'snapshot'); // '/api/cameras/abc-123/snapshot'
 * cameraEndpoint('abc-123', 'zones'); // '/api/cameras/abc-123/zones'
 * ```
 */
export function cameraEndpoint(): '/api/cameras';
export function cameraEndpoint(id: string): CameraEndpoint;
export function cameraEndpoint(
  id: string,
  action: 'snapshot' | 'zones' | 'baseline/activity' | 'baseline/classes'
): CameraEndpoint;
export function cameraEndpoint(
  id?: string,
  action?: 'snapshot' | 'zones' | 'baseline/activity' | 'baseline/classes'
): CameraEndpoint {
  if (!id) {
    return '/api/cameras';
  }
  if (!action) {
    return `/api/cameras/${id}` as CameraEndpoint;
  }
  return `/api/cameras/${id}/${action}` as CameraEndpoint;
}

/**
 * Builds event API endpoints with type safety.
 *
 * @param id - Optional event ID
 * @param action - Optional action (detections, stats, search, export)
 * @returns Type-safe endpoint string
 *
 * @example
 * ```ts
 * eventEndpoint(); // '/api/events'
 * eventEndpoint(123); // '/api/events/123'
 * eventEndpoint(123, 'detections'); // '/api/events/123/detections'
 * eventEndpoint(undefined, 'stats'); // '/api/events/stats'
 * ```
 */
export function eventEndpoint(): '/api/events';
export function eventEndpoint(id: number): EventEndpoint;
export function eventEndpoint(id: number, action: 'detections'): EventEndpoint;
export function eventEndpoint(id: undefined, action: 'stats' | 'search' | 'export'): EventEndpoint;
export function eventEndpoint(
  id?: number,
  action?: 'detections' | 'stats' | 'search' | 'export'
): EventEndpoint {
  if (id === undefined && !action) {
    return '/api/events';
  }
  if (id === undefined && action) {
    return `/api/events/${action}` as EventEndpoint;
  }
  if (id !== undefined && !action) {
    return `/api/events/${id}` as EventEndpoint;
  }
  return `/api/events/${id}/${action}` as EventEndpoint;
}

/**
 * Builds detection API endpoints with type safety.
 *
 * @param id - Optional detection ID
 * @param action - Action (stats, image, video, video/thumbnail, enrichment)
 * @returns Type-safe endpoint string
 *
 * @example
 * ```ts
 * detectionEndpoint(undefined, 'stats'); // '/api/detections/stats'
 * detectionEndpoint(123, 'image'); // '/api/detections/123/image'
 * detectionEndpoint(123, 'video'); // '/api/detections/123/video'
 * detectionEndpoint(123, 'enrichment'); // '/api/detections/123/enrichment'
 * ```
 */
export function detectionEndpoint(id: undefined, action: 'stats'): '/api/detections/stats';
export function detectionEndpoint(id: number, action: 'enrichment'): EnrichmentEndpoint;
export function detectionEndpoint(
  id: number,
  action: 'image' | 'video' | 'video/thumbnail'
): DetectionEndpoint;
export function detectionEndpoint(
  id?: number,
  action?: 'stats' | 'image' | 'video' | 'video/thumbnail' | 'enrichment'
): DetectionEndpoint | EnrichmentEndpoint {
  if (id === undefined && action === 'stats') {
    return '/api/detections/stats';
  }
  return `/api/detections/${id}/${action}` as DetectionEndpoint | EnrichmentEndpoint;
}

/**
 * Builds enrichment API endpoints with type safety.
 *
 * @param detectionId - Detection ID
 * @returns Type-safe endpoint string
 *
 * @example
 * ```ts
 * enrichmentEndpoint(123); // '/api/detections/123/enrichment'
 * ```
 */
export function enrichmentEndpoint(detectionId: number): EnrichmentEndpoint {
  return `/api/detections/${detectionId}/enrichment` as EnrichmentEndpoint;
}

/**
 * Builds zone API endpoints with type safety.
 *
 * @param cameraId - Camera ID
 * @param zoneId - Optional zone ID
 * @returns Type-safe endpoint string
 *
 * @example
 * ```ts
 * zoneEndpoint('cam-123'); // '/api/cameras/cam-123/zones'
 * zoneEndpoint('cam-123', 'zone-456'); // '/api/cameras/cam-123/zones/zone-456'
 * ```
 */
export function zoneEndpoint(cameraId: string): ZoneEndpoint;
export function zoneEndpoint(cameraId: string, zoneId: string): ZoneEndpoint;
export function zoneEndpoint(cameraId: string, zoneId?: string): ZoneEndpoint {
  if (!zoneId) {
    return `/api/cameras/${cameraId}/zones` as ZoneEndpoint;
  }
  return `/api/cameras/${cameraId}/zones/${zoneId}` as ZoneEndpoint;
}

/**
 * Builds alert rule API endpoints with type safety.
 *
 * @param id - Optional alert rule ID
 * @param action - Optional action (test)
 * @returns Type-safe endpoint string
 *
 * @example
 * ```ts
 * alertRuleEndpoint(); // '/api/alerts/rules'
 * alertRuleEndpoint('rule-123'); // '/api/alerts/rules/rule-123'
 * alertRuleEndpoint('rule-123', 'test'); // '/api/alerts/rules/rule-123/test'
 * ```
 */
export function alertRuleEndpoint(): '/api/alerts/rules';
export function alertRuleEndpoint(id: string): AlertRuleEndpoint;
export function alertRuleEndpoint(id: string, action: 'test'): AlertRuleEndpoint;
export function alertRuleEndpoint(id?: string, action?: 'test'): AlertRuleEndpoint {
  if (!id) {
    return '/api/alerts/rules';
  }
  if (!action) {
    return `/api/alerts/rules/${id}` as AlertRuleEndpoint;
  }
  return `/api/alerts/rules/${id}/${action}` as AlertRuleEndpoint;
}

// ============================================================================
// Type-Safe API Client Functions
// ============================================================================

/**
 * Type-safe GET request function.
 *
 * @param endpoint - API endpoint (validated at compile time)
 * @param options - Optional fetch options
 * @returns Promise with correctly typed response
 *
 * @example
 * ```ts
 * const cameras = await apiGet('/api/cameras'); // Type: CameraListResponse
 * const camera = await apiGet('/api/cameras/abc-123'); // Type: Camera
 * ```
 */
export function apiGet<T extends ApiEndpoint>(
  endpoint: T,
  _options?: RequestInit
): Promise<EndpointResponseType<T>> {
  // Implementation would call the actual fetch API
  // This is a type-safe wrapper that ensures correct return types
  throw new Error(`apiGet not implemented - use existing fetchApi for now: ${endpoint}`);
}

/**
 * Type-safe POST request function.
 *
 * @param endpoint - API endpoint
 * @param body - Request body
 * @param options - Optional fetch options
 * @returns Promise with response
 */
export function apiPost<T extends ApiEndpoint>(
  endpoint: T,
  _body?: unknown,
  _options?: RequestInit
): Promise<EndpointResponseType<T>> {
  throw new Error(`apiPost not implemented - use existing fetchApi for now: ${endpoint}`);
}

/**
 * Type-safe PATCH request function.
 *
 * @param endpoint - API endpoint
 * @param body - Request body
 * @param options - Optional fetch options
 * @returns Promise with response
 */
export function apiPatch<T extends ApiEndpoint>(
  endpoint: T,
  _body?: unknown,
  _options?: RequestInit
): Promise<EndpointResponseType<T>> {
  throw new Error(`apiPatch not implemented - use existing fetchApi for now: ${endpoint}`);
}

/**
 * Type-safe PUT request function.
 *
 * @param endpoint - API endpoint
 * @param body - Request body
 * @param options - Optional fetch options
 * @returns Promise with response
 */
export function apiPut<T extends ApiEndpoint>(
  endpoint: T,
  _body?: unknown,
  _options?: RequestInit
): Promise<EndpointResponseType<T>> {
  throw new Error(`apiPut not implemented - use existing fetchApi for now: ${endpoint}`);
}

/**
 * Type-safe DELETE request function.
 *
 * @param endpoint - API endpoint
 * @param options - Optional fetch options
 * @returns Promise with void
 */
export function apiDelete<T extends ApiEndpoint>(
  endpoint: T,
  _options?: RequestInit
): Promise<void> {
  throw new Error(`apiDelete not implemented - use existing fetchApi for now: ${endpoint}`);
}
