/**
 * Generated Zod schemas for events.py
 *
 * AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
 * Run: uv run python scripts/generate_zod_schemas.py
 *
 * Source: backend/api/schemas/events.py
 */

import { z } from 'zod';

// =============================================================================
// Enum Schemas
// =============================================================================

/** EnrichmentStatusEnum enum values */
export const ENRICHMENT_STATUS_ENUM_VALUES = ['full', 'partial', 'failed', 'skipped'] as const;

/** EnrichmentStatusEnum Zod schema */
export const enrichmentStatusEnumSchema = z.enum(ENRICHMENT_STATUS_ENUM_VALUES);

/** EnrichmentStatusEnum type */
export type EnrichmentStatusEnumValue = (typeof ENRICHMENT_STATUS_ENUM_VALUES)[number];

// =============================================================================
// Schema Definitions
// =============================================================================

/**
 * Schema for enrichment status in event responses (NEM-1672).
 *
 * Provides visibility into which enrichment models succeeded/failed
 * for a given event, instead of silently degrading.
 */
export const enrichmentStatusResponseSchema = z.object({
  /** Overall enrichment status (full, partial, failed, skipped) */
  status: enrichmentStatusEnumSchema,
  /** List of enrichment models that succeeded */
  successful_models: z.array(z.string()).default([]),
  /** List of enrichment models that failed */
  failed_models: z.array(z.string()).default([]),
  /** Model name to error message mapping */
  errors: z.record(z.string(), z.unknown()).default({}),
  /** Success rate (0.0 to 1.0) */
  success_rate: z.number().min(0.0).max(1.0),
});

/**
 * Schema for event response.
 */
export const eventResponseSchema = z.object({
  /** Event ID */
  id: z.number().int(),
  /** Normalized camera ID (e.g., 'front_door') */
  camera_id: z.string(),
  /** Event start timestamp */
  started_at: z.string().datetime(),
  /** Event end timestamp */
  ended_at: z.string().datetime().nullable().default(null),
  /** Risk score (0-100) */
  risk_score: z.number().int().nullable().default(null),
  /** Risk level (low, medium, high, critical) */
  risk_level: z.string().nullable().default(null),
  /** LLM-generated event summary */
  summary: z.string().nullable().default(null),
  /** LLM reasoning for risk score */
  reasoning: z.string().nullable().default(null),
  /** Full prompt sent to Nemotron LLM (for debugging/improvement) */
  llm_prompt: z.string().nullable().default(null),
  /** Whether event has been reviewed */
  reviewed: z.boolean().default(false),
  /** User notes for the event */
  notes: z.string().nullable().default(null),
  /** Number of detections in this event */
  detection_count: z.number().int().default(0),
  /** List of detection IDs associated with this event */
  detection_ids: z.array(z.number().int()).default([]),
  /** URL to thumbnail image (first detection's media) */
  thumbnail_url: z.string().nullable().default(null),
  /** Enrichment pipeline status (NEM-1672) - shows which models succeeded/failed */
  enrichment_status: enrichmentStatusResponseSchema.nullable().default(null),
});

/**
 * Schema for updating an event (PATCH).
 */
export const eventUpdateSchema = z.object({
  /** Mark event as reviewed or not reviewed */
  reviewed: z.boolean().nullable().default(null).optional(),
  /** User notes for the event */
  notes: z.string().nullable().default(null).optional(),
});

/**
 * Schema for event list response with pagination.
 *
 * NEM-2075: Standardized pagination envelope with items + pagination structure.
 * Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
 * Use cursor-based pagination for better performance with large datasets.
 */
export const eventListResponseSchema = z.object({
  /** List of events */
  items: z.array(eventResponseSchema),
  /** Pagination metadata */
  pagination: z.unknown(),
  /** Warning message when using deprecated offset pagination */
  deprecation_warning: z.string().nullable().default(null),
});

/**
 * Schema for events count by risk level.
 */
export const eventsByRiskLevelSchema = z.object({
  /** Number of critical risk events */
  critical: z.number().int().default(0),
  /** Number of high risk events */
  high: z.number().int().default(0),
  /** Number of medium risk events */
  medium: z.number().int().default(0),
  /** Number of low risk events */
  low: z.number().int().default(0),
});

/**
 * Schema for events count by camera.
 */
export const eventsByCameraSchema = z.object({
  /** Normalized camera ID (e.g., 'front_door') */
  camera_id: z.string(),
  /** Camera name */
  camera_name: z.string(),
  /** Number of events for this camera */
  event_count: z.number().int(),
});

/**
 * Schema for aggregated event statistics.
 */
export const eventStatsResponseSchema = z.object({
  /** Total number of events */
  total_events: z.number().int(),
  /** Events grouped by risk level */
  events_by_risk_level: z.unknown(),
  /** Events grouped by camera */
  events_by_camera: z.array(eventsByCameraSchema),
});

/**
 * Schema for listing soft-deleted events (trash view).
 *
 * NEM-1955: Provides a trash view of soft-deleted events that can be restored.
 * Events are ordered by deleted_at descending (most recently deleted first).
 * NEM-2075: Standardized pagination envelope with items + pagination structure.
 */
export const deletedEventsListResponseSchema = z.object({
  /** List of soft-deleted events */
  items: z.array(eventResponseSchema),
  /** Pagination metadata */
  pagination: z.unknown(),
});

// =============================================================================
// Type Exports
// =============================================================================

/** Type for EnrichmentStatusResponse */
export type EnrichmentStatusResponseInput = z.input<typeof enrichmentStatusResponseSchema>;
export type EnrichmentStatusResponseOutput = z.output<typeof enrichmentStatusResponseSchema>;

/** Type for EventResponse */
export type EventResponseInput = z.input<typeof eventResponseSchema>;
export type EventResponseOutput = z.output<typeof eventResponseSchema>;

/** Type for EventUpdate */
export type EventUpdateInput = z.input<typeof eventUpdateSchema>;
export type EventUpdateOutput = z.output<typeof eventUpdateSchema>;

/** Type for EventListResponse */
export type EventListResponseInput = z.input<typeof eventListResponseSchema>;
export type EventListResponseOutput = z.output<typeof eventListResponseSchema>;

/** Type for EventsByRiskLevel */
export type EventsByRiskLevelInput = z.input<typeof eventsByRiskLevelSchema>;
export type EventsByRiskLevelOutput = z.output<typeof eventsByRiskLevelSchema>;

/** Type for EventsByCamera */
export type EventsByCameraInput = z.input<typeof eventsByCameraSchema>;
export type EventsByCameraOutput = z.output<typeof eventsByCameraSchema>;

/** Type for EventStatsResponse */
export type EventStatsResponseInput = z.input<typeof eventStatsResponseSchema>;
export type EventStatsResponseOutput = z.output<typeof eventStatsResponseSchema>;

/** Type for DeletedEventsListResponse */
export type DeletedEventsListResponseInput = z.input<typeof deletedEventsListResponseSchema>;
export type DeletedEventsListResponseOutput = z.output<typeof deletedEventsListResponseSchema>;
