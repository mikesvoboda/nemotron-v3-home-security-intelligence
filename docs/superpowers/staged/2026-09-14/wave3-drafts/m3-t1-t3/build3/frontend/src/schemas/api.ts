/**
 * Consolidated API Response Schemas
 *
 * This module provides Zod schemas for validating API responses. These schemas
 * are shared between frontend validation (forms) and API response parsing,
 * ensuring consistency between client and server data structures.
 *
 * Benefits:
 * - Runtime validation of API responses catches backend/frontend contract violations
 * - Same schemas used for form validation and response parsing
 * - Type-safe with inferred TypeScript types
 * - Automatic error messages for invalid responses
 *
 * @example
 * ```typescript
 * import { eventResponseSchema, EventResponse } from '@/schemas/api';
 *
 * // API client with runtime validation
 * export async function getEvent(id: string): Promise<EventResponse> {
 *   const response = await fetch(`/api/events/${id}`);
 *   const data = await response.json();
 *   return eventResponseSchema.parse(data);
 * }
 * ```
 */

import { z } from 'zod';

import {
  uuid,
  cameraId,
  eventId,
  detectionId,
  zoneId,
  alertRuleId,
  entityId,
  riskScore,
  riskLevel,
  optionalRiskScore,
  optionalRiskLevel,
  confidence,
  optionalConfidence,
  timestamp,
  optionalTimestamp,
  objectType,
  cameraStatus,
  alertSeverity,
  dayOfWeek,
  boundingBox,
  pageNumber,
  totalCount,
} from './primitives';

// =============================================================================
// Camera Schemas
// =============================================================================

/**
 * Camera response schema - validates camera data from API.
 * Matches backend CameraResponse Pydantic model.
 */
export const cameraResponseSchema = z.object({
  id: cameraId,
  name: z.string().min(1),
  folder_path: z.string().min(1),
  status: cameraStatus,
  created_at: timestamp,
  updated_at: optionalTimestamp,
  thumbnail_url: z.string().nullable().optional(),
  stream_url: z.string().nullable().optional(),
  detection_count: z.number().int().min(0).optional(),
  last_detection_at: optionalTimestamp,
});

/** Type inferred from camera response schema */
export type CameraResponse = z.infer<typeof cameraResponseSchema>;

/**
 * Camera list response schema - paginated camera list.
 */
export const cameraListResponseSchema = z.object({
  items: z.array(cameraResponseSchema),
  total: totalCount,
  page: pageNumber,
  size: z.number().int().min(1),
  pages: z.number().int().min(0),
});

/** Type inferred from camera list response schema */
export type CameraListResponse = z.infer<typeof cameraListResponseSchema>;

// =============================================================================
// Detection Schemas
// =============================================================================

/**
 * Detection response schema - validates detection data from API.
 * Matches backend DetectionResponse Pydantic model.
 */
export const detectionResponseSchema = z.object({
  id: detectionId,
  event_id: eventId,
  label: z.string(),
  confidence: confidence,
  bbox: boundingBox.nullable().optional(),
  frame_number: z.number().int().min(0).nullable().optional(),
  frame_timestamp: optionalTimestamp,
  thumbnail_path: z.string().nullable().optional(),
  created_at: timestamp,
  // Optional enrichments
  entity_id: entityId.nullable().optional(),
  track_id: z.number().int().nullable().optional(),
});

/** Type inferred from detection response schema */
export type DetectionResponse = z.infer<typeof detectionResponseSchema>;

/**
 * Detection list response schema - paginated detection list.
 */
export const detectionListResponseSchema = z.object({
  items: z.array(detectionResponseSchema),
  total: totalCount,
  page: pageNumber,
  size: z.number().int().min(1),
  pages: z.number().int().min(0),
});

/** Type inferred from detection list response schema */
export type DetectionListResponse = z.infer<typeof detectionListResponseSchema>;

// =============================================================================
// Event Schemas
// =============================================================================

/**
 * Risk analysis nested schema.
 */
export const riskAnalysisSchema = z.object({
  risk_score: riskScore,
  risk_level: riskLevel,
  analysis_text: z.string().nullable().optional(),
  threat_summary: z.string().nullable().optional(),
  recommended_actions: z.array(z.string()).nullable().optional(),
  confidence_factors: z.record(z.string(), z.number()).nullable().optional(),
});

/** Type inferred from risk analysis schema */
export type RiskAnalysis = z.infer<typeof riskAnalysisSchema>;

/**
 * Event response schema - validates event data from API.
 * Matches backend EventResponse Pydantic model.
 */
export const eventResponseSchema = z.object({
  id: eventId,
  camera_id: cameraId,
  started_at: timestamp,
  ended_at: optionalTimestamp,
  risk_score: optionalRiskScore,
  risk_level: optionalRiskLevel,
  status: z.enum(['pending', 'processing', 'analyzed', 'error', 'archived']),
  detection_count: z.number().int().min(0),
  thumbnail_path: z.string().nullable().optional(),
  video_path: z.string().nullable().optional(),
  created_at: timestamp,
  updated_at: optionalTimestamp,
  // Version for optimistic locking (NEM-3625)
  version: z.number().int().min(1).optional(),
  // Nested objects
  camera: cameraResponseSchema.optional(),
  risk_analysis: riskAnalysisSchema.nullable().optional(),
  // User interaction fields
  flagged: z.boolean().optional(),
  flagged_at: optionalTimestamp,
  flag_reason: z.string().nullable().optional(),
  reviewed_at: optionalTimestamp,
  reviewed_by: z.string().nullable().optional(),
});

/** Type inferred from event response schema */
export type EventResponse = z.infer<typeof eventResponseSchema>;

/**
 * Event list response schema - paginated event list.
 */
export const eventListResponseSchema = z.object({
  items: z.array(eventResponseSchema),
  total: totalCount,
  page: pageNumber,
  size: z.number().int().min(1),
  pages: z.number().int().min(0),
});

/** Type inferred from event list response schema */
export type EventListResponse = z.infer<typeof eventListResponseSchema>;

/**
 * Events by risk level schema - for statistics.
 */
export const eventsByRiskLevelSchema = z.object({
  low: z.number().int().min(0),
  medium: z.number().int().min(0),
  high: z.number().int().min(0),
  critical: z.number().int().min(0),
});

/** Type inferred from events by risk level schema */
export type EventsByRiskLevel = z.infer<typeof eventsByRiskLevelSchema>;

/**
 * Events by camera schema - for statistics.
 */
export const eventsByCameraSchema = z.record(z.string(), z.number().int().min(0));

/** Type inferred from events by camera schema */
export type EventsByCamera = z.infer<typeof eventsByCameraSchema>;

/**
 * Event stats response schema.
 */
export const eventStatsResponseSchema = z.object({
  total_events: z.number().int().min(0),
  events_by_risk_level: eventsByRiskLevelSchema,
  events_by_camera: eventsByCameraSchema,
  average_risk_score: z.number().min(0).max(100).nullable(),
  time_range_start: optionalTimestamp,
  time_range_end: optionalTimestamp,
});

/** Type inferred from event stats response schema */
export type EventStatsResponse = z.infer<typeof eventStatsResponseSchema>;

// =============================================================================
// Alert Rule Schemas
// =============================================================================

/**
 * Alert rule schedule schema.
 */
export const alertRuleScheduleResponseSchema = z.object({
  days: z.array(dayOfWeek).nullable().optional(),
  start_time: z.string().nullable().optional(),
  end_time: z.string().nullable().optional(),
  timezone: z.string(),
});

/** Type inferred from alert rule schedule schema */
export type AlertRuleScheduleResponse = z.infer<typeof alertRuleScheduleResponseSchema>;

/**
 * Alert rule response schema - validates alert rule data from API.
 * Matches backend AlertRuleResponse Pydantic model.
 */
export const alertRuleResponseSchema = z.object({
  id: alertRuleId,
  name: z.string().min(1),
  description: z.string().nullable().optional(),
  enabled: z.boolean(),
  severity: alertSeverity,
  risk_threshold: z.number().int().min(0).max(100).nullable().optional(),
  object_types: z.array(z.string()).nullable().optional(),
  camera_ids: z.array(cameraId).nullable().optional(),
  zone_ids: z.array(zoneId).nullable().optional(),
  min_confidence: optionalConfidence,
  schedule: alertRuleScheduleResponseSchema.nullable().optional(),
  dedup_key_template: z.string(),
  cooldown_seconds: z.number().int().min(0),
  channels: z.array(z.string()),
  created_at: timestamp,
  updated_at: optionalTimestamp,
  last_triggered_at: optionalTimestamp,
  trigger_count: z.number().int().min(0).optional(),
});

/** Type inferred from alert rule response schema */
export type AlertRuleResponse = z.infer<typeof alertRuleResponseSchema>;

/**
 * Alert rule list response schema - paginated alert rule list.
 */
export const alertRuleListResponseSchema = z.object({
  items: z.array(alertRuleResponseSchema),
  total: totalCount,
  page: pageNumber,
  size: z.number().int().min(1),
  pages: z.number().int().min(0),
});

/** Type inferred from alert rule list response schema */
export type AlertRuleListResponse = z.infer<typeof alertRuleListResponseSchema>;

// =============================================================================
// Alert Schemas
// =============================================================================

/**
 * Alert response schema - validates alert data from API.
 * Matches backend AlertResponse Pydantic model.
 */
export const alertResponseSchema = z.object({
  id: uuid,
  rule_id: alertRuleId,
  event_id: eventId,
  camera_id: cameraId,
  severity: alertSeverity,
  title: z.string(),
  message: z.string().nullable().optional(),
  risk_score: riskScore,
  acknowledged: z.boolean(),
  acknowledged_at: optionalTimestamp,
  acknowledged_by: z.string().nullable().optional(),
  resolved: z.boolean(),
  resolved_at: optionalTimestamp,
  resolved_by: z.string().nullable().optional(),
  dismissed: z.boolean(),
  dismissed_at: optionalTimestamp,
  dismissed_by: z.string().nullable().optional(),
  created_at: timestamp,
  // Version for optimistic locking
  version: z.number().int().min(1).optional(),
});

/** Type inferred from alert response schema */
export type AlertResponse = z.infer<typeof alertResponseSchema>;

/**
 * Alert list response schema - paginated alert list.
 */
export const alertListResponseSchema = z.object({
  items: z.array(alertResponseSchema),
  total: totalCount,
  page: pageNumber,
  size: z.number().int().min(1),
  pages: z.number().int().min(0),
});

/** Type inferred from alert list response schema */
export type AlertListResponse = z.infer<typeof alertListResponseSchema>;

// =============================================================================
// Zone Schemas
// =============================================================================

/**
 * Zone point schema - coordinate in a zone polygon.
 */
export const zonePointSchema = z.object({
  x: z.number().min(0).max(1),
  y: z.number().min(0).max(1),
});

/** Type inferred from zone point schema */
export type ZonePoint = z.infer<typeof zonePointSchema>;

/**
 * Zone response schema - validates zone data from API.
 * Matches backend ZoneResponse Pydantic model.
 */
export const zoneResponseSchema = z.object({
  id: zoneId,
  camera_id: cameraId,
  name: z.string().min(1),
  description: z.string().nullable().optional(),
  points: z.array(zonePointSchema).min(3),
  color: z.string().optional(),
  enabled: z.boolean(),
  alert_on_entry: z.boolean(),
  alert_on_exit: z.boolean(),
  alert_on_loitering: z.boolean(),
  loitering_threshold_seconds: z.number().int().min(0).optional(),
  object_types: z.array(objectType).nullable().optional(),
  created_at: timestamp,
  updated_at: optionalTimestamp,
});

/** Type inferred from zone response schema */
export type ZoneResponse = z.infer<typeof zoneResponseSchema>;

/**
 * Zone list response schema - paginated zone list.
 */
export const zoneListResponseSchema = z.object({
  items: z.array(zoneResponseSchema),
  total: totalCount,
  page: pageNumber,
  size: z.number().int().min(1),
  pages: z.number().int().min(0),
});

/** Type inferred from zone list response schema */
export type ZoneListResponse = z.infer<typeof zoneListResponseSchema>;

// =============================================================================
// Entity Schemas
// =============================================================================

/**
 * Entity response schema - validates entity (re-ID) data from API.
 * Matches backend EntityResponse Pydantic model.
 */
export const entityResponseSchema = z.object({
  id: entityId,
  label: z.string(),
  object_type: objectType,
  first_seen_at: timestamp,
  last_seen_at: timestamp,
  camera_ids: z.array(cameraId),
  detection_count: z.number().int().min(0),
  average_confidence: z.number().min(0).max(1).optional(),
  embedding: z.array(z.number()).nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).nullable().optional(),
  created_at: timestamp,
  updated_at: optionalTimestamp,
});

/** Type inferred from entity response schema */
export type EntityResponse = z.infer<typeof entityResponseSchema>;

/**
 * Entity list response schema - paginated entity list.
 */
export const entityListResponseSchema = z.object({
  items: z.array(entityResponseSchema),
  total: totalCount,
  page: pageNumber,
  size: z.number().int().min(1),
  pages: z.number().int().min(0),
});

/** Type inferred from entity list response schema */
export type EntityListResponse = z.infer<typeof entityListResponseSchema>;

// =============================================================================
// Health/System Schemas
// =============================================================================

/**
 * Service status schema for health check response.
 */
export const serviceStatusSchema = z.object({
  status: z.enum(['healthy', 'degraded', 'unhealthy']),
  message: z.string().nullable().optional(),
  details: z.record(z.string(), z.unknown()).nullable().optional(),
});

/** Type inferred from service status schema */
export type ServiceStatus = z.infer<typeof serviceStatusSchema>;

/**
 * Health response schema - validates health check data from API.
 */
export const healthResponseSchema = z.object({
  status: z.enum(['healthy', 'degraded', 'unhealthy']),
  version: z.string(),
  uptime_seconds: z.number().min(0),
  timestamp: timestamp,
  services: z.record(z.string(), serviceStatusSchema),
});

/** Type inferred from health response schema */
export type HealthResponse = z.infer<typeof healthResponseSchema>;

/**
 * GPU stats schema.
 */
export const gpuStatsSchema = z.object({
  index: z.number().int().min(0),
  name: z.string(),
  utilization_gpu: z.number().min(0).max(100),
  utilization_memory: z.number().min(0).max(100),
  memory_total_mb: z.number().min(0),
  memory_used_mb: z.number().min(0),
  memory_free_mb: z.number().min(0),
  temperature_c: z.number().nullable().optional(),
  power_draw_w: z.number().nullable().optional(),
  power_limit_w: z.number().nullable().optional(),
});

/** Type inferred from GPU stats schema */
export type GpuStats = z.infer<typeof gpuStatsSchema>;

/**
 * GPU stats response schema.
 */
export const gpuStatsResponseSchema = z.object({
  gpus: z.array(gpuStatsSchema),
  timestamp: timestamp,
});

/** Type inferred from GPU stats response schema */
export type GpuStatsResponse = z.infer<typeof gpuStatsResponseSchema>;

// =============================================================================
// Pagination Helpers
// =============================================================================

/**
 * Creates a paginated response schema for any item schema.
 *
 * @param itemSchema - The Zod schema for individual items
 * @returns Paginated response schema
 *
 * @example
 * ```typescript
 * const myPaginatedResponse = paginatedResponse(myItemSchema);
 * type MyPaginatedResponse = z.infer<typeof myPaginatedResponse>;
 * ```
 */
export function paginatedResponse<T extends z.ZodTypeAny>(itemSchema: T) {
  return z.object({
    items: z.array(itemSchema),
    total: totalCount,
    page: pageNumber,
    size: z.number().int().min(1),
    pages: z.number().int().min(0),
  });
}

/**
 * Creates a cursor-paginated response schema for any item schema.
 *
 * @param itemSchema - The Zod schema for individual items
 * @returns Cursor-paginated response schema
 */
export function cursorPaginatedResponse<T extends z.ZodTypeAny>(itemSchema: T) {
  return z.object({
    items: z.array(itemSchema),
    next_cursor: z.string().nullable(),
    has_more: z.boolean(),
  });
}

// =============================================================================
// API Error Schemas
// =============================================================================

/**
 * Validation error detail schema.
 */
export const validationErrorDetailSchema = z.object({
  loc: z.array(z.union([z.string(), z.number()])),
  msg: z.string(),
  type: z.string(),
});

/** Type inferred from validation error detail schema */
export type ValidationErrorDetail = z.infer<typeof validationErrorDetailSchema>;

/**
 * API error response schema (422 validation errors).
 */
export const validationErrorResponseSchema = z.object({
  detail: z.array(validationErrorDetailSchema),
});

/** Type inferred from validation error response schema */
export type ValidationErrorResponse = z.infer<typeof validationErrorResponseSchema>;

/**
 * Generic API error schema.
 */
export const apiErrorSchema = z.object({
  detail: z.string(),
  status_code: z.number().int().optional(),
  error_code: z.string().optional(),
});

/** Type inferred from API error schema */
export type ApiError = z.infer<typeof apiErrorSchema>;

// =============================================================================
// Safe Parse Helper
// =============================================================================

/**
 * Safely parses API response data with schema validation.
 * Returns the parsed data or throws a descriptive error.
 *
 * @param schema - Zod schema to validate against
 * @param data - Data to parse
 * @param context - Optional context for error messages
 * @returns Parsed and validated data
 *
 * @example
 * ```typescript
 * const event = parseApiResponse(eventResponseSchema, data, 'getEvent');
 * ```
 */
export function parseApiResponse<T extends z.ZodTypeAny>(
  schema: T,
  data: unknown,
  context?: string
): z.infer<T> {
  const result = schema.safeParse(data);
  if (!result.success) {
    const errorMessage = context
      ? `API response validation failed for ${context}`
      : 'API response validation failed';
    console.error(errorMessage, result.error.issues);
    throw new Error(`${errorMessage}: ${result.error.issues.map((i) => i.message).join(', ')}`);
  }
  return result.data;
}

/**
 * Safely parses API response data, returning null on validation failure.
 * Logs warning but doesn't throw.
 *
 * @param schema - Zod schema to validate against
 * @param data - Data to parse
 * @param context - Optional context for warning messages
 * @returns Parsed data or null
 */
export function safeParseApiResponse<T extends z.ZodTypeAny>(
  schema: T,
  data: unknown,
  context?: string
): z.infer<T> | null {
  const result = schema.safeParse(data);
  if (!result.success) {
    const errorMessage = context
      ? `API response validation warning for ${context}`
      : 'API response validation warning';
    console.warn(errorMessage, result.error.issues);
    return null;
  }
  return result.data;
}
