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

// System types
export type HealthResponse = components['schemas']['HealthResponse'];
export type ServiceStatus = components['schemas']['ServiceStatus'];
export type GPUStats = components['schemas']['GPUStatsResponse'];
export type GPUStatsSample = components['schemas']['GPUStatsSample'];
export type GPUStatsHistoryResponse = components['schemas']['GPUStatsHistoryResponse'];
export type SystemConfig = components['schemas']['ConfigResponse'];
export type SystemConfigUpdate = components['schemas']['ConfigUpdateRequest'];
export type SystemStats = components['schemas']['SystemStatsResponse'];
export type LivenessResponse = components['schemas']['LivenessResponse'];
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

// Import the components type for use in type aliases
import type { components } from './api';
