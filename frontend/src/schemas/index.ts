/**
 * Frontend Zod validation schemas.
 *
 * This module exports Zod schemas that mirror backend Pydantic models.
 * All schemas are designed to provide client-side validation that matches
 * server-side validation rules exactly.
 *
<<<<<<< HEAD
 * ## Modules
 *
 * - **primitives**: Reusable schema primitives (IDs, scores, timestamps, etc.)
 * - **camera**: Camera CRUD form validation schemas
 * - **alertRule**: Alert rule form validation schemas
 * - **api**: API response validation schemas
 *
 * @example
 * ```typescript
 * // Form validation with primitives
 * import { riskScore, riskLevel, cameraId } from '@/schemas';
 *
 * // API response parsing
 * import { eventResponseSchema, parseApiResponse } from '@/schemas';
 * const event = parseApiResponse(eventResponseSchema, data);
 *
 * // Form schemas
 * import { cameraFormSchema, alertRuleFormSchema } from '@/schemas';
 * ```
 */

// =============================================================================
// Schema Primitives (NEM-3819)
// =============================================================================

export {
  // ID Primitives
  uuid,
  cameraId,
  eventId,
  detectionId,
  zoneId,
  alertRuleId,
  entityId,
  batchId,
  // Risk Assessment Primitives
  riskScore,
  optionalRiskScore,
  riskLevel,
  optionalRiskLevel,
  RISK_SCORE_CONSTRAINTS,
  RISK_LEVEL_VALUES,
  // Confidence Primitives
  confidence,
  optionalConfidence,
  CONFIDENCE_CONSTRAINTS,
  // Timestamp Primitives
  timestamp,
  optionalTimestamp,
  isoDateString,
  optionalIsoDateString,
  // Object Type Primitives
  objectType,
  objectTypes,
  optionalObjectTypes,
  OBJECT_TYPE_VALUES,
  // Camera Status Primitives
  cameraStatus,
  CAMERA_STATUS_VALUES,
  // Alert Severity Primitives
  alertSeverity,
  ALERT_SEVERITY_VALUES,
  // Day of Week Primitives
  dayOfWeek,
  daysOfWeek,
  DAY_OF_WEEK_VALUES,
  // String Primitives
  nonEmptyString,
  stringWithLength,
  // Bounding Box Primitives
  boundingBox,
  optionalBoundingBox,
  normalizedCoordinate,
  // Pagination Primitives
  pageNumber,
  pageSize,
  totalCount,
  paginationCursor,
  // Time String Primitives
  timeString,
  optionalTimeString,
} from './primitives';

export type {
  RiskLevelValue,
  ObjectTypeValue,
  CameraStatusValue,
  AlertSeverityValue,
  DayOfWeekValue,
  UUID,
  CameraIdType,
  EventIdType,
  RiskScoreType,
  ConfidenceType,
  TimestampType,
  BoundingBoxType,
} from './primitives';

// =============================================================================
// Camera Form Schemas
// =============================================================================

export {
  // Constants
  CAMERA_NAME_CONSTRAINTS,
  CAMERA_FOLDER_PATH_CONSTRAINTS,
  CAMERA_STATUS_VALUES as CAMERA_FORM_STATUS_VALUES,
  // Schemas
  cameraStatusSchema,
  cameraNameSchema,
  cameraFolderPathSchema,
  cameraCreateSchema,
  cameraUpdateSchema,
  cameraFormSchema,
} from './camera';

export type {
  CameraStatusValue as CameraFormStatusValue,
  CameraCreateInput,
  CameraCreateOutput,
  CameraUpdateInput,
  CameraUpdateOutput,
  CameraFormInput,
  CameraFormOutput,
} from './camera';

// =============================================================================
// Alert Rule Form Schemas
// =============================================================================

export {
  // Constants
  ALERT_RULE_NAME_CONSTRAINTS,
  RISK_THRESHOLD_CONSTRAINTS,
  MIN_CONFIDENCE_CONSTRAINTS,
  COOLDOWN_SECONDS_CONSTRAINTS,
  DEDUP_KEY_TEMPLATE_CONSTRAINTS,
  ALERT_SEVERITY_VALUES as ALERT_RULE_SEVERITY_VALUES,
  VALID_DAYS,
  // Schemas
  alertSeveritySchema,
  dayOfWeekSchema,
  alertRuleNameSchema,
  riskThresholdSchema,
  minConfidenceSchema,
  cooldownSecondsSchema,
  dedupKeyTemplateSchema,
  timeStringSchema,
  daysArraySchema,
  alertRuleScheduleSchema,
  alertRuleCreateSchema,
  alertRuleUpdateSchema,
  alertRuleFormSchema,
} from './alertRule';

export type {
  AlertSeverityValue as AlertRuleSeverityValue,
  DayOfWeekValue as AlertRuleDayValue,
  AlertRuleCreateInput,
  AlertRuleCreateOutput,
  AlertRuleUpdateInput,
  AlertRuleUpdateOutput,
  AlertRuleFormInput,
  AlertRuleFormOutput,
  AlertRuleScheduleInput,
  AlertRuleScheduleOutput,
} from './alertRule';

// =============================================================================
// API Response Schemas (NEM-3824)
// =============================================================================

export {
  // Camera Response Schemas
  cameraResponseSchema,
  cameraListResponseSchema,
  // Detection Response Schemas
  detectionResponseSchema,
  detectionListResponseSchema,
  // Event Response Schemas
  riskAnalysisSchema,
  eventResponseSchema,
  eventListResponseSchema,
  eventsByRiskLevelSchema,
  eventsByCameraSchema,
  eventStatsResponseSchema,
  // Alert Rule Response Schemas
  alertRuleScheduleResponseSchema,
  alertRuleResponseSchema,
  alertRuleListResponseSchema,
  // Alert Response Schemas
  alertResponseSchema,
  alertListResponseSchema,
  // Zone Response Schemas
  zonePointSchema,
  zoneResponseSchema,
  zoneListResponseSchema,
  // Entity Response Schemas
  entityResponseSchema,
  entityListResponseSchema,
  // Health Response Schemas
  serviceStatusSchema,
  healthResponseSchema,
  gpuStatsSchema,
  gpuStatsResponseSchema,
  // Pagination Helpers
  paginatedResponse,
  cursorPaginatedResponse,
  // Error Schemas
  validationErrorDetailSchema,
  validationErrorResponseSchema,
  apiErrorSchema,
  // Parse Helpers
  parseApiResponse,
  safeParseApiResponse,
} from './api';

export type {
  CameraResponse,
  CameraListResponse,
  DetectionResponse,
  DetectionListResponse,
  RiskAnalysis,
  EventResponse,
  EventListResponse,
  EventsByRiskLevel,
  EventsByCamera,
  EventStatsResponse,
  AlertRuleScheduleResponse,
  AlertRuleResponse,
  AlertRuleListResponse,
  AlertResponse,
  AlertListResponse,
  ZonePoint,
  ZoneResponse,
  ZoneListResponse,
  EntityResponse,
  EntityListResponse,
  ServiceStatus,
  HealthResponse,
  GpuStats,
  GpuStatsResponse,
  ValidationErrorDetail,
  ValidationErrorResponse,
  ApiError,
} from './api';

// =============================================================================
// Alert Schemas (NEM-3825)
// =============================================================================

export * from './alert';

// =============================================================================
// Zone Form Schemas (NEM-3825)
// =============================================================================

export * from './zone';

// =============================================================================
// Async Validation Utilities (NEM-3825)
// =============================================================================

export * from './asyncValidation';
