/**
 * Types Module
 *
 * Central export point for all frontend types.
 * Import types from this module for convenient access.
 *
 * @example
 * ```typescript
 * import { Entity, EntityMatch, EntityHistory } from '../types';
 * import type { AsyncState, RiskLevel } from '../types';
 * ```
 */

// ============================================================================
// Generated API Types (from OpenAPI spec)
// ============================================================================

export * from './generated';

// ============================================================================
// Entity Re-Identification Types
// ============================================================================

export type {
  // Core entity types
  Entity,
  EntityAppearance,
  EntitySummary,
  EntityDetail,
  // Response types
  EntityListResponse,
  EntityHistoryResponse,
  // Query types
  EntityQueryParams,
  // Additional entity types
  EntityMatch,
  EntityHistory,
} from './entity';

// ============================================================================
// Async State Types
// ============================================================================

export type {
  AsyncState,
  IdleState,
  LoadingState,
  ErrorState,
  SuccessState,
  AsyncStatus,
  RefreshableState,
  RefreshingState,
  PaginatedData,
  PaginatedState,
  AsyncHookReturn,
} from './async';

export {
  idle,
  loading,
  success,
  failure,
  isIdle,
  isLoading,
  isError,
  isSuccess,
  hasData,
  getData,
  getError,
  mapData,
  matchState,
  isRefreshing,
  refreshing,
  paginatedSuccess,
  createAsyncHookReturn,
} from './async';

// ============================================================================
// Branded Types
// ============================================================================

export type {
  Brand,
  CameraId,
  EventId,
  DetectionId,
  ZoneId,
  AlertRuleId,
  EntityId,
  BatchId,
  Unbrand,
  StringEntityId,
  NumericEntityId,
  AnyEntityId,
} from './branded';

export {
  createCameraId,
  createEventId,
  createDetectionId,
  createZoneId,
  createAlertRuleId,
  createEntityId,
  createBatchId,
  unwrapStringId,
  unwrapNumberId,
  isSameId,
  isSameNumericId,
} from './branded';

// ============================================================================
// Type Guards
// ============================================================================

export {
  isString,
  isNumber,
  isBoolean,
  isNull,
  isUndefined,
  isNullish,
  isDefined,
  isPlainObject,
  isArray,
  isArrayOf,
  isNonEmptyArray,
  hasProperty,
  hasPropertyOfType,
  hasProperties,
  hasOptionalPropertyOfType,
  oneOf,
  isStringOrNumber,
  isApiError,
  isPaginatedResponse,
  getProperty,
  getTypedProperty,
  getRequiredProperty,
  validateObject,
  createObjectGuard,
  isDate,
  isISODateString,
  isPositiveNumber,
  isNonNegativeNumber,
  isInteger,
  isPositiveInteger,
  isNonEmptyString,
  isUUID,
  literalUnion,
  numericLiteralUnion,
} from './guards';

export type { ApiErrorShape, PaginatedResponseShape, TypeGuard, GuardedType, ObjectSchema } from './guards';

// ============================================================================
// Constants and Utilities
// ============================================================================

export {
  RISK_LEVELS,
  RISK_LEVEL_CONFIG,
  HEALTH_STATUSES,
  HEALTH_STATUS_CONFIG,
  CONTAINER_STATUSES,
  CONTAINER_STATUS_CONFIG,
  OBJECT_TYPES,
  OBJECT_TYPE_CONFIG,
  CONFIDENCE_LEVELS,
  CONFIDENCE_THRESHOLDS,
  CONFIDENCE_LEVEL_CONFIG,
  WS_MESSAGE_TYPES,
  DAYS_OF_WEEK,
  DAY_OF_WEEK_LABELS,
  DAY_OF_WEEK_SHORT,
  ALERT_SEVERITIES,
  ALERT_SEVERITY_CONFIG,
  MODEL_STATUSES,
  MODEL_STATUS_CONFIG,
  TIME_RANGES,
  TIME_RANGE_CONFIG,
  isRiskLevel,
  isHealthStatus,
  isContainerStatus,
  isObjectType,
  isModelStatus,
  isDayOfWeek,
  getRiskLevelFromScore,
  getConfidenceLevelFromScore,
  assertNever,
} from './constants';

export type {
  RiskLevel,
  RiskLevelConfig,
  HealthStatus,
  HealthStatusConfig,
  ContainerStatus,
  ContainerStatusConfig,
  ObjectType,
  ObjectTypeConfig,
  ConfidenceLevel,
  WsMessageType,
  DayOfWeek,
  AlertSeverity,
  ModelStatus,
  TimeRange,
} from './constants';

// ============================================================================
// Result Types (for error handling)
// ============================================================================

export type { Result, OkResult, ErrResult } from './result';

export { Ok, Err, isOk, isErr, unwrap, unwrapOr, unwrapErr, map, mapErr, andThen, orElse, match } from './result';

// ============================================================================
// WebSocket Types
// ============================================================================

export type {
  WebSocketEventMap,
  ServiceStatusChangedPayload,
  SceneChangeDetectedPayload,
} from './websocket-events';

// ============================================================================
// Enrichment Types
// ============================================================================

export type {
  PoseKeypoint,
  PoseEnrichment,
  VehicleEnrichment,
  PersonEnrichment,
} from './enrichment';

// ============================================================================
// Notification Preferences Types
// ============================================================================

export type {
  NotificationPreferences,
  CameraNotificationSetting,
  QuietHoursPeriod,
} from './notificationPreferences';

// ============================================================================
// Prompt Management Types
// ============================================================================

export type {
  PromptVersionInfo,
  PromptTestResult,
  ModelPromptConfig,
} from './promptManagement';

// ============================================================================
// Performance Types
// ============================================================================

export type { PerformanceAlert, AiModelMetrics } from './performance';

// ============================================================================
// Rate Limit Types
// ============================================================================

export type { RateLimitInfo, ApiResponse } from './rate-limit';
