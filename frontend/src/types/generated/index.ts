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
 */

export type { paths, components, operations } from './api';

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
export type ServiceStatus = components['schemas']['ServiceStatus'];
// HealthServiceStatus is an alias for ServiceStatus for backward compatibility
export type HealthServiceStatus = ServiceStatus;
export type GPUStats = components['schemas']['GPUStatsResponse'];
export type GPUStatsSample = components['schemas']['GPUStatsSample'];
export type GPUStatsHistoryResponse = components['schemas']['GPUStatsHistoryResponse'];
export type SystemConfig = components['schemas']['ConfigResponse'];
export type SystemConfigUpdate = components['schemas']['ConfigUpdateRequest'];
export type SystemStats = components['schemas']['SystemStatsResponse'];
export type ReadinessResponse = components['schemas']['ReadinessResponse'];
export type WorkerStatus = components['schemas']['WorkerStatus'];

// Telemetry types
export type TelemetryResponse = components['schemas']['TelemetryResponse'];
export type QueueDepths = components['schemas']['QueueDepths'];
export type PipelineLatencies = components['schemas']['PipelineLatencies'];
export type StageLatency = components['schemas']['StageLatency'];

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

// Alert Rule types
export type AlertRule = components['schemas']['AlertRuleResponse'];
export type AlertRuleCreate = components['schemas']['AlertRuleCreate'];
export type AlertRuleUpdate = components['schemas']['AlertRuleUpdate'];
export type AlertRuleListResponse = components['schemas']['AlertRuleListResponse'];
export type AlertRuleSchedule = components['schemas']['AlertRuleSchedule'];
export type AlertSeverity = components['schemas']['AlertSeverity'];

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

// Import the components type for use in type aliases
import type { components } from './api';
