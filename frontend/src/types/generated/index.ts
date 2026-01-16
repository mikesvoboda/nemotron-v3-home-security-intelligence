/**
 * Generated API Types
 *
 * This module re-exports types from the auto-generated OpenAPI types file.
 * The types are generated from the backend OpenAPI specification using:
 *
 *   ./scripts/generate-types.sh
 *
 * DO NOT modify this file manually. Update the backend schemas and regenerate.
 *
 * @see ./api.ts - Full auto-generated types from openapi-typescript
 * @see ./websocket.ts - Auto-generated WebSocket types from generate-ws-types.py
 */

export type { paths, components, operations } from './api';

// Re-export WebSocket types (generated from backend Pydantic schemas)
// These are not covered by OpenAPI, so they have their own generator
export type {
  // Enums and constants
  RiskLevel,
  WebSocketMessageType,
  WebSocketServiceStatus,
  WebSocketErrorCodeType,
  // Data payload interfaces
  WebSocketEventData,
  WebSocketServiceStatusData,
  WebSocketSceneChangeData,
  // Message envelope interfaces
  WebSocketPingMessage,
  WebSocketPongResponse,
  WebSocketSubscribeMessage,
  WebSocketUnsubscribeMessage,
  WebSocketErrorResponse,
  WebSocketEventMessage,
  WebSocketServiceStatusMessage,
  WebSocketSceneChangeMessage,
  WebSocketMessage,
  // Discriminated union types
  WebSocketServerMessage,
  WebSocketClientMessage,
  AnyWebSocketMessage,
  MessageByType,
  MessageHandler,
  MessageHandlerMap,
} from './websocket';

export {
  // Error code constants
  WebSocketErrorCode,
  // Type guards
  isEventMessage,
  isServiceStatusMessage,
  isSceneChangeMessage,
  isPingMessage,
  isPongMessage,
  isErrorMessage,
  // Utilities
  createMessageDispatcher,
  assertNever,
} from './websocket';

// Re-export component schemas for convenient access
// These match the backend Pydantic schemas in backend/api/schemas/

// Camera types
export type Camera = components['schemas']['CameraResponse'];
export type CameraCreate = components['schemas']['CameraCreate'];
export type CameraUpdate = components['schemas']['CameraUpdate'];
export type CameraListResponse = components['schemas']['CameraListResponse'];

// Event types
export type Event = components['schemas']['EventResponse'];
export type EventUpdate = components['schemas']['EventUpdate'];
export type EventListResponse = components['schemas']['EventListResponse'];
export type EventStatsResponse = components['schemas']['EventStatsResponse'];
export type EventsByRiskLevel = components['schemas']['EventsByRiskLevel'];
export type EventsByCamera = components['schemas']['EventsByCamera'];

// Detection types
export type Detection = components['schemas']['DetectionResponse'];
export type DetectionListResponse = components['schemas']['DetectionListResponse'];
export type DetectionSearchResult = components['schemas']['DetectionSearchResult'];
export type DetectionSearchResponse = components['schemas']['DetectionSearchResponse'];
export type DetectionLabelCount = components['schemas']['DetectionLabelCount'];
export type DetectionLabelsResponse = components['schemas']['DetectionLabelsResponse'];

// Enrichment types
export type EnrichmentResponse = components['schemas']['EnrichmentResponse'];
export type EventEnrichmentsResponse = components['schemas']['EventEnrichmentsResponse'];
export type LicensePlateEnrichment = components['schemas']['LicensePlateEnrichment'];
export type FaceEnrichment = components['schemas']['FaceEnrichment'];
export type VehicleEnrichment = components['schemas']['VehicleEnrichment'];
export type ClothingEnrichment = components['schemas']['ClothingEnrichment'];
export type ViolenceEnrichment = components['schemas']['ViolenceEnrichment'];
export type WeatherEnrichment = components['schemas']['WeatherEnrichment'];
export type PoseEnrichment = components['schemas']['PoseEnrichment'];
export type DepthEnrichment = components['schemas']['DepthEnrichment'];
export type ImageQualityEnrichment = components['schemas']['ImageQualityEnrichment'];
export type PetEnrichment = components['schemas']['PetEnrichment'];

// System types
export type HealthResponse = components['schemas']['HealthResponse'];
// ServiceStatus is an object type with {status, message?, details?} for HealthResponse.services
// (Backend renamed from ServiceStatus to HealthCheckServiceStatus to avoid collision)
export type ServiceStatus = components['schemas']['HealthCheckServiceStatus'];
// ContainerServiceStatus is the enum used by the orchestrator: running, starting, unhealthy, etc.
export type ContainerServiceStatus = components['schemas']['ContainerServiceStatus'];
export type GPUStats = components['schemas']['GPUStatsResponse'];
export type GPUStatsSample = components['schemas']['GPUStatsSample'];
export type GPUStatsHistoryResponse = components['schemas']['GPUStatsHistoryResponse'];
export type SystemConfig = components['schemas']['ConfigResponse'];
export type SystemConfigUpdate = components['schemas']['ConfigUpdateRequest'];
export type SystemStats = components['schemas']['SystemStatsResponse'];
export type ReadinessResponse = components['schemas']['ReadinessResponse'];
// WorkerStatus from system health endpoint (has message, name, running)
export type WorkerStatus = components['schemas']['WorkerStatus'];
// Pipeline worker status from debug endpoint (has error_count, last_activity, name, running)
export type PipelineWorkerStatus = components['schemas']['PipelineWorkerStatus'];

// Telemetry types
export type TelemetryResponse = components['schemas']['TelemetryResponse'];
export type QueueDepths = components['schemas']['QueueDepths'];
export type PipelineLatencies = components['schemas']['PipelineLatencies'];
export type StageLatency = components['schemas']['StageLatency'];

// Pipeline Latency types
export type PipelineLatencyResponse = components['schemas']['PipelineLatencyResponse'];
export type PipelineLatencyHistoryResponse =
  components['schemas']['PipelineLatencyHistoryResponse'];
export type PipelineStageLatency = components['schemas']['PipelineStageLatency'];
export type LatencyHistorySnapshot = components['schemas']['LatencyHistorySnapshot'];
export type LatencyHistoryStageStats = components['schemas']['LatencyHistoryStageStats'];

// Log types
export type LogEntry = components['schemas']['LogEntry'];
export type LogsResponse = components['schemas']['LogsResponse'];
export type LogStats = components['schemas']['LogStats'];
export type FrontendLogCreate = components['schemas']['FrontendLogCreate'];

// DLQ types
export type DLQJobResponse = components['schemas']['DLQJobResponse'];
export type DLQJobsResponse = components['schemas']['DLQJobsResponse'];
export type DLQStatsResponse = components['schemas']['DLQStatsResponse'];
export type DLQClearResponse = components['schemas']['DLQClearResponse'];
export type DLQRequeueResponse = components['schemas']['DLQRequeueResponse'];
export type DLQName = components['schemas']['DLQName'];

// Media types
export type MediaErrorResponse = components['schemas']['MediaErrorResponse'];

// Cleanup types
export type CleanupResponse = components['schemas']['CleanupResponse'];
export type CleanupStatusResponse = components['schemas']['CleanupStatusResponse'];
export type OrphanedFileCleanupResponse = components['schemas']['OrphanedFileCleanupResponse'];

// Job types
export type JobResponse = components['schemas']['JobResponse'];
export type JobListResponse = components['schemas']['JobListResponse'];
export type JobStatusEnum = components['schemas']['JobStatusEnum'];

// Validation error type
export type HTTPValidationError = components['schemas']['HTTPValidationError'];
export type ValidationError = components['schemas']['ValidationError'];

// Search types
export type SearchResult = components['schemas']['SearchResult'];
export type SearchResponse = components['schemas']['SearchResponse'];

// Audit types
export type AuditLogResponse = components['schemas']['AuditLogResponse'];
export type AuditLogListResponse = components['schemas']['AuditLogListResponse'];
export type AuditLogStats = components['schemas']['AuditLogStats'];

// Alert Rule types - base generated types
type GeneratedAlertRuleResponse = components['schemas']['AlertRuleResponse'];
type GeneratedAlertRuleCreate = components['schemas']['AlertRuleCreate'];
type GeneratedAlertRuleUpdate = components['schemas']['AlertRuleUpdate'];
type GeneratedAlertRuleListResponse = components['schemas']['AlertRuleListResponse'];
export type AlertSeverity = components['schemas']['AlertSeverity'];

/**
 * Day of the week type for schedule configuration.
 * Constrains days to valid lowercase day names.
 */
export type DayOfWeek =
  | 'monday'
  | 'tuesday'
  | 'wednesday'
  | 'thursday'
  | 'friday'
  | 'saturday'
  | 'sunday';

/**
 * Alert rule schedule type with properly constrained days.
 * Overrides the auto-generated type to use DayOfWeek union instead of string[].
 *
 * @see backend/api/schemas/alert_rules.py - AlertRuleSchedule
 */
export interface AlertRuleSchedule {
  /** Days of week when rule is active (empty/null = all days) */
  days?: DayOfWeek[] | null;
  /** Start time in HH:MM format */
  start_time?: string | null;
  /** End time in HH:MM format */
  end_time?: string | null;
  /** Timezone for the schedule (IANA timezone string) */
  timezone: string;
}

/**
 * Alert rule response type with properly typed schedule.
 * Overrides the auto-generated schedule type to use our DayOfWeek-constrained AlertRuleSchedule.
 */
export type AlertRule = Omit<GeneratedAlertRuleResponse, 'schedule'> & {
  schedule?: AlertRuleSchedule | null;
};

/**
 * Alert rule create type with properly typed schedule.
 */
export type AlertRuleCreate = Omit<GeneratedAlertRuleCreate, 'schedule'> & {
  schedule?: AlertRuleSchedule | null;
};

/**
 * Alert rule update type with properly typed schedule.
 */
export type AlertRuleUpdate = Omit<GeneratedAlertRuleUpdate, 'schedule'> & {
  schedule?: AlertRuleSchedule | null;
};

/**
 * Alert rule list response with properly typed items.
 */
export type AlertRuleListResponse = Omit<GeneratedAlertRuleListResponse, 'items'> & {
  items: AlertRule[];
};

// Circuit Breaker types
export type CircuitBreakerStateEnum = components['schemas']['CircuitBreakerStateEnum'];
export type CircuitBreakerConfigResponse = components['schemas']['CircuitBreakerConfigResponse'];
export type CircuitBreakerStatusResponse = components['schemas']['CircuitBreakerStatusResponse'];
export type CircuitBreakersResponse = components['schemas']['CircuitBreakersResponse'];
export type CircuitBreakerResetResponse = components['schemas']['CircuitBreakerResetResponse'];

// Severity types
export type SeverityEnum = components['schemas']['SeverityEnum'];
export type SeverityDefinitionResponse = components['schemas']['SeverityDefinitionResponse'];
export type SeverityThresholds = components['schemas']['SeverityThresholds'];
export type SeverityMetadataResponse = components['schemas']['SeverityMetadataResponse'];

// Scene Change types
export type SceneChangeResponse = components['schemas']['SceneChangeResponse'];
export type SceneChangeListResponse = components['schemas']['SceneChangeListResponse'];
export type SceneChangeAcknowledgeResponse =
  components['schemas']['SceneChangeAcknowledgeResponse'];

// Zone types
export type Zone = components['schemas']['ZoneResponse'];
export type ZoneCreate = components['schemas']['ZoneCreate'];
export type ZoneUpdate = components['schemas']['ZoneUpdate'];
export type ZoneListResponse = components['schemas']['ZoneListResponse'];
export type ZoneShape = components['schemas']['ZoneShape'];
export type ZoneType = components['schemas']['ZoneType'];

// Model Zoo types
export type ModelStatusResponse = components['schemas']['ModelStatusResponse'];
export type ModelRegistryResponse = components['schemas']['ModelRegistryResponse'];
export type ModelStatusEnum = components['schemas']['ModelStatusEnum'];

// AI Audit types (manually defined - pending OpenAPI type generation)
// These match backend/api/schemas/ai_audit.py

/** Model contribution flags */
export interface AiAuditModelContributions {
  rtdetr: boolean;
  florence: boolean;
  clip: boolean;
  violence: boolean;
  clothing: boolean;
  vehicle: boolean;
  pet: boolean;
  weather: boolean;
  image_quality: boolean;
  zones: boolean;
  baseline: boolean;
  cross_camera: boolean;
}

/** Self-evaluation quality scores (1-5 scale) */
export interface AiAuditQualityScores {
  context_usage: number | null;
  reasoning_coherence: number | null;
  risk_justification: number | null;
  consistency: number | null;
  overall: number | null;
}

/** Prompt improvement suggestions from self-evaluation */
export interface AiAuditPromptImprovements {
  missing_context: string[];
  confusing_sections: string[];
  unused_data: string[];
  format_suggestions: string[];
  model_gaps: string[];
}

/** Full audit response for a single event */
export interface AiAuditEventAuditResponse {
  id: number;
  event_id: number;
  audited_at: string;
  is_fully_evaluated: boolean;
  contributions: AiAuditModelContributions;
  prompt_length: number;
  prompt_token_estimate: number;
  enrichment_utilization: number;
  scores: AiAuditQualityScores;
  consistency_risk_score: number | null;
  consistency_diff: number | null;
  self_eval_critique: string | null;
  improvements: AiAuditPromptImprovements;
}

/** Aggregate audit statistics */
export interface AiAuditStatsResponse {
  total_events: number;
  audited_events: number;
  fully_evaluated_events: number;
  avg_quality_score: number | null;
  avg_consistency_rate: number | null;
  avg_enrichment_utilization: number | null;
  model_contribution_rates: Record<string, number>;
  audits_by_day: Array<Record<string, unknown>>;
}

/** Single entry in model leaderboard */
export interface AiAuditModelLeaderboardEntry {
  model_name: string;
  contribution_rate: number;
  quality_correlation: number | null;
  event_count: number;
}

/** Model leaderboard response */
export interface AiAuditLeaderboardResponse {
  entries: AiAuditModelLeaderboardEntry[];
  period_days: number;
}

/** Single recommendation item */
export interface AiAuditRecommendationItem {
  category: string;
  suggestion: string;
  frequency: number;
  priority: 'high' | 'medium' | 'low';
}

/** Aggregated recommendations response */
export interface AiAuditRecommendationsResponse {
  recommendations: AiAuditRecommendationItem[];
  total_events_analyzed: number;
}

// Notification Preferences types
export type NotificationPreferencesResponse =
  components['schemas']['NotificationPreferencesResponse'];
export type NotificationPreferencesUpdate = components['schemas']['NotificationPreferencesUpdate'];
export type CameraNotificationSettingResponse =
  components['schemas']['CameraNotificationSettingResponse'];
export type CameraNotificationSettingUpdate =
  components['schemas']['CameraNotificationSettingUpdate'];
export type CameraNotificationSettingsListResponse =
  components['schemas']['CameraNotificationSettingsListResponse'];
export type QuietHoursPeriodCreate = components['schemas']['QuietHoursPeriodCreate'];
export type QuietHoursPeriodResponse = components['schemas']['QuietHoursPeriodResponse'];
export type QuietHoursPeriodsListResponse = components['schemas']['QuietHoursPeriodsListResponse'];

// Entity Re-Identification types
export type EntityAppearance = components['schemas']['EntityAppearance'];
export type EntitySummary = components['schemas']['EntitySummary'];
export type EntityDetail = components['schemas']['EntityDetail'];
export type EntityListResponse = components['schemas']['EntityListResponse'];
export type EntityHistoryResponse = components['schemas']['EntityHistoryResponse'];
export type PaginationInfo = components['schemas']['PaginationInfo'];

// Calibration types (manually defined - pending OpenAPI type generation)
// These match backend/api/schemas/calibration.py

/** User calibration response with all threshold settings */
export interface CalibrationResponse {
  /** Calibration record ID */
  id: number;
  /** User identifier (default for single-user system) */
  user_id: string;
  /** Upper bound for low risk (0-100) */
  low_threshold: number;
  /** Upper bound for medium risk (0-100) */
  medium_threshold: number;
  /** Upper bound for high risk (0-100) */
  high_threshold: number;
  /** Learning rate for threshold adjustment (0.0-1.0) */
  decay_factor: number;
  /** Total false positives reported */
  false_positive_count: number;
  /** Total missed threats reported */
  missed_threat_count: number;
  /** When the calibration record was created */
  created_at: string;
  /** When the calibration was last modified */
  updated_at: string;
}

/** Request schema for updating calibration thresholds */
export interface CalibrationUpdate {
  /** Upper bound for low risk (0-100, optional) */
  low_threshold?: number | null;
  /** Upper bound for medium risk (0-100, optional) */
  medium_threshold?: number | null;
  /** Upper bound for high risk (0-100, optional) */
  high_threshold?: number | null;
  /** Learning rate for threshold adjustment (0.0-1.0, optional) */
  decay_factor?: number | null;
}

/** Default calibration threshold values */
export interface CalibrationDefaultsResponse {
  /** Default upper bound for low risk */
  low_threshold: number;
  /** Default upper bound for medium risk */
  medium_threshold: number;
  /** Default upper bound for high risk */
  high_threshold: number;
  /** Default learning rate for threshold adjustment */
  decay_factor: number;
}

/** Response for calibration reset operation */
export interface CalibrationResetResponse {
  /** Success message */
  message: string;
  /** Reset calibration data */
  calibration: CalibrationResponse;
}

// Event Feedback types
export type EventFeedbackCreate = components['schemas']['EventFeedbackCreate'];
export type EventFeedbackResponse = components['schemas']['EventFeedbackResponse'];
export type FeedbackType = components['schemas']['FeedbackType'];
export type FeedbackStatsResponse = components['schemas']['FeedbackStatsResponse'];

// Import the components type for use in type aliases
import type { components } from './api';
