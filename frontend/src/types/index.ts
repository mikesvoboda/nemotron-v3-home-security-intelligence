/**
 * Frontend Type System
 *
 * This module provides centralized exports for all frontend types including:
 * - Branded types for entity IDs (type-safe, prevents ID mixing)
 * - Discriminated unions for WebSocket messages
 * - Async state management types
 * - Type-safe constants with const assertions
 * - Type guards for runtime type checking
 * - Generated API types from backend OpenAPI spec
 *
 * @example
 * ```ts
 * // Import from centralized types
 * import {
 *   type CameraId,
 *   type EventId,
 *   createCameraId,
 *   createEventId,
 *   isEventMessage,
 *   success,
 *   isSuccess,
 *   RISK_LEVELS,
 *   isRiskLevel,
 * } from '../types';
 * ```
 */

// ============================================================================
// Branded Types (Entity IDs)
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
  StringEntityId,
  NumericEntityId,
  AnyEntityId,
  Unbrand,
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
// WebSocket Message Types (Discriminated Unions)
// ============================================================================

export type {
  RiskLevel as WebSocketRiskLevel,
  SecurityEventData,
  EventMessage,
  GpuStatusData,
  CameraStatusData,
  QueueStatusData,
  HealthStatus as WebSocketHealthStatus,
  SystemStatusData,
  SystemStatusMessage,
  ContainerStatus as WebSocketContainerStatus,
  ServiceStatusData,
  ServiceStatusMessage,
  HeartbeatMessage,
  PongMessage,
  ErrorMessage as WebSocketErrorMessage,
  EventsChannelMessage,
  SystemChannelMessage,
  WebSocketMessage,
  WebSocketMessageType,
  MessageData,
  MessageByType,
  MessageHandler,
  MessageHandlerMap,
} from './websocket';

export {
  isEventMessage,
  isSystemStatusMessage,
  isServiceStatusMessage,
  isHeartbeatMessage,
  isPongMessage,
  isErrorMessage,
  isWebSocketMessage,
  createMessageDispatcher,
} from './websocket';

// ============================================================================
// Async State Types (Discriminated Unions)
// ============================================================================

export type {
  IdleState,
  LoadingState,
  ErrorState,
  SuccessState,
  AsyncState,
  AsyncStatus,
  RefreshingState,
  RefreshableState,
  PaginatedData,
  PaginatedState,
  AsyncHookReturn,
} from './async';

export {
  idle,
  loading,
  failure,
  success,
  isIdle,
  isLoading,
  isError,
  isSuccess,
  hasData,
  getData,
  getError,
  mapData,
  matchState,
  refreshing,
  isRefreshing,
  paginatedSuccess,
  createAsyncHookReturn,
} from './async';

// ============================================================================
// Constants (Const Assertions and Literal Types)
// ============================================================================

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

export {
  // Risk levels
  RISK_LEVELS,
  RISK_LEVEL_CONFIG,
  isRiskLevel,
  getRiskLevelFromScore,
  // Health status
  HEALTH_STATUSES,
  HEALTH_STATUS_CONFIG,
  isHealthStatus,
  // Container status
  CONTAINER_STATUSES,
  CONTAINER_STATUS_CONFIG,
  isContainerStatus,
  // Object types
  OBJECT_TYPES,
  OBJECT_TYPE_CONFIG,
  isObjectType,
  // Confidence levels
  CONFIDENCE_LEVELS,
  CONFIDENCE_THRESHOLDS,
  CONFIDENCE_LEVEL_CONFIG,
  getConfidenceLevelFromScore,
  // WebSocket message types
  WS_MESSAGE_TYPES,
  // Days of week
  DAYS_OF_WEEK,
  DAY_OF_WEEK_LABELS,
  DAY_OF_WEEK_SHORT,
  isDayOfWeek,
  // Alert severity
  ALERT_SEVERITIES,
  ALERT_SEVERITY_CONFIG,
  // Model status
  MODEL_STATUSES,
  MODEL_STATUS_CONFIG,
  isModelStatus,
  // Time ranges
  TIME_RANGES,
  TIME_RANGE_CONFIG,
  // Utility
  assertNever,
} from './constants';

// ============================================================================
// Type Guards (Runtime Type Checking)
// ============================================================================

export type {
  TypeGuard,
  GuardedType,
  ApiErrorShape,
  PaginatedResponseShape,
} from './guards';

export {
  // Primitives
  isString,
  isNumber,
  isBoolean,
  isNull,
  isUndefined,
  isNullish,
  isDefined,
  // Objects
  isPlainObject,
  isArray,
  isArrayOf,
  isNonEmptyArray,
  // Properties
  hasProperty,
  hasPropertyOfType,
  hasProperties,
  hasOptionalPropertyOfType,
  // Compound
  oneOf,
  isStringOrNumber,
  // API
  isApiError,
  isPaginatedResponse,
  // Safe access
  getProperty,
  getTypedProperty,
  getRequiredProperty,
  // Object validation
  validateObject,
  createObjectGuard,
  // Special values
  isDate,
  isISODateString,
  isPositiveNumber,
  isNonNegativeNumber,
  isInteger,
  isPositiveInteger,
  isNonEmptyString,
  isUUID,
  // Literal unions
  literalUnion,
  numericLiteralUnion,
} from './guards';

// ============================================================================
// Generated API Types
// ============================================================================

export * from './generated';

// ============================================================================
// Performance Types
// ============================================================================

export type { PerformanceAlert, AiModelMetrics, NemotronMetrics } from './performance';
export type { TimeRange as PerformanceTimeRange } from './performance';

// ============================================================================
// Enrichment Types
// ============================================================================

export type {
  VehicleType,
  VehicleDamageType,
  VehicleEnrichment,
  PetType,
  PetEnrichment,
  PersonAction,
  CarryingItem,
  PersonEnrichment,
  LicensePlateEnrichment,
  WeatherCondition,
  WeatherEnrichment,
  ImageQualityIssue,
  ImageQualityEnrichment,
  EnrichmentData,
} from './enrichment';

export {
  // Constants
  VEHICLE_TYPES,
  VEHICLE_DAMAGE_TYPES,
  PET_TYPES,
  PERSON_ACTIONS,
  CARRYING_ITEMS,
  WEATHER_CONDITIONS,
  IMAGE_QUALITY_ISSUES,
  // Type guards
  isVehicleEnrichment,
  isPetEnrichment,
  isPersonEnrichment,
  isLicensePlateEnrichment,
  isWeatherEnrichment,
  isImageQualityEnrichment,
  isEnrichmentData,
  // Utilities
  getEnrichmentValue,
  hasAnyEnrichment,
  countEnrichments,
} from './enrichment';
