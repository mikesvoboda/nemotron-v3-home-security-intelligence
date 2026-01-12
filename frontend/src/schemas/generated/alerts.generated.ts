/**
 * Generated Zod schemas for alerts.py
 *
 * AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
 * Run: uv run python scripts/generate_zod_schemas.py
 *
 * Source: backend/api/schemas/alerts.py
 */

import { z } from 'zod';

// =============================================================================
// Enum Schemas
// =============================================================================

/** AlertSeverity enum values */
export const ALERT_SEVERITY_VALUES = ['low', 'medium', 'high', 'critical'] as const;

/** AlertSeverity Zod schema */
export const alertSeveritySchema = z.enum(ALERT_SEVERITY_VALUES);

/** AlertSeverity type */
export type AlertSeverityValue = (typeof ALERT_SEVERITY_VALUES)[number];

/** AlertStatus enum values */
export const ALERT_STATUS_VALUES = ['pending', 'delivered', 'acknowledged', 'dismissed'] as const;

/** AlertStatus Zod schema */
export const alertStatusSchema = z.enum(ALERT_STATUS_VALUES);

/** AlertStatus type */
export type AlertStatusValue = (typeof ALERT_STATUS_VALUES)[number];

// =============================================================================
// Schema Definitions
// =============================================================================

/**
 * Schema for alert rule schedule (time-based conditions).
 *
 * If start_time > end_time, the schedule spans midnight (e.g., 22:00-06:00).
 * Empty days array means all days. No schedule = always active (vacation mode).
 *
 * Validation:
 * - Days must be valid day names (monday-sunday)
 * - Times must be valid HH:MM format with hours 00-23, minutes 00-59
 * - Start and end times are validated but can span midnight
 */
export const alertRuleScheduleSchema = z.object({
  /** Days of week when rule is active (empty = all days). Values: monday, tuesday, wednesday, thursday, friday, saturday, sunday */
  days: z.array(z.string()).nullable().default(null),
  /** Start time in HH:MM format (00:00-23:59) */
  start_time: z.string().regex(/^\\d{2}:\\d{2}$/).nullable().default(null),
  /** End time in HH:MM format (00:00-23:59) */
  end_time: z.string().regex(/^\\d{2}:\\d{2}$/).nullable().default(null),
  /** Timezone for time evaluation */
  timezone: z.string().default('UTC'),
});

/**
 * Schema for legacy alert rule conditions (backward compatibility).
 *
 * New rules should use explicit fields on AlertRuleCreate/AlertRuleUpdate.
 * This schema is kept for backward compatibility with existing rules.
 */
export const alertRuleConditionsSchema = z.object({
  /** Minimum risk score to trigger alert */
  risk_threshold: z.number().int().min(0).max(100).nullable().default(null),
  /** Object types that trigger alerts (e.g., person, vehicle) */
  object_types: z.array(z.string()).nullable().default(null),
  /** Specific camera IDs that trigger alerts */
  camera_ids: z.array(z.string()).nullable().default(null),
  /** Time ranges when alerts are active (start/end in HH:MM format) */
  time_ranges: z.array(z.unknown()).nullable().default(null),
});

/**
 * Schema for creating an alert rule.
 *
 * All conditions use AND logic - all specified conditions must match for the rule to trigger.
 * Leave a condition as null/empty to not filter on that criterion.
 */
export const alertRuleCreateSchema = z.object({
  /** Rule name */
  name: z.string().min(1).max(255),
  /** Rule description */
  description: z.string().nullable().default(null),
  /** Whether the rule is active */
  enabled: z.boolean().default(true),
  /** Severity level for triggered alerts */
  severity: alertSeveritySchema,
  /** Alert when risk_score >= threshold */
  risk_threshold: z.number().int().min(0).max(100).nullable().default(null),
  /** Object types to match (e.g., ['person', 'vehicle']) */
  object_types: z.array(z.string()).nullable().default(null),
  /** Camera IDs to apply rule to (empty = all cameras) */
  camera_ids: z.array(z.string()).nullable().default(null),
  /** Zone IDs to match (empty = any zone) */
  zone_ids: z.array(z.string()).nullable().default(null),
  /** Minimum detection confidence (0.0-1.0) */
  min_confidence: z.number().min(0.0).max(1.0).nullable().default(null),
  /** Time-based conditions (null = always active) */
  schedule: alertRuleScheduleSchema.nullable().default(null),
  /** Legacy conditions (use explicit fields instead) */
  conditions: alertRuleConditionsSchema.nullable().default(null),
  /** Template for dedup key. Variables: {camera_id}, {rule_id}, {object_type} */
  dedup_key_template: z.string().max(255).default('{camera_id}:{rule_id}'),
  /** Minimum seconds between duplicate alerts */
  cooldown_seconds: z.number().int().min(0).default(300),
  /** Notification channels for this rule */
  channels: z.array(z.string()).default([]),
});

/**
 * Schema for updating an alert rule (PATCH).
 *
 * Only provided fields will be updated. Null values clear the field.
 */
export const alertRuleUpdateSchema = z.object({
  /** Rule name */
  name: z.string().min(1).max(255).nullable().default(null).optional(),
  /** Rule description */
  description: z.string().nullable().default(null).optional(),
  /** Whether the rule is active */
  enabled: z.boolean().nullable().default(null).optional(),
  /** Severity level */
  severity: alertSeveritySchema.nullable().default(null).optional(),
  /** Alert when risk_score >= threshold */
  risk_threshold: z.number().int().min(0).max(100).nullable().default(null).optional(),
  /** Object types to match */
  object_types: z.array(z.string()).nullable().default(null).optional(),
  /** Camera IDs to apply rule to */
  camera_ids: z.array(z.string()).nullable().default(null).optional(),
  /** Zone IDs to match */
  zone_ids: z.array(z.string()).nullable().default(null).optional(),
  /** Minimum detection confidence */
  min_confidence: z.number().min(0.0).max(1.0).nullable().default(null).optional(),
  /** Time-based conditions */
  schedule: alertRuleScheduleSchema.nullable().default(null).optional(),
  /** Legacy conditions */
  conditions: alertRuleConditionsSchema.nullable().default(null).optional(),
  /** Template for dedup key */
  dedup_key_template: z.string().max(255).nullable().default(null).optional(),
  /** Minimum seconds between duplicate alerts */
  cooldown_seconds: z.number().int().min(0).nullable().default(null).optional(),
  /** Notification channels for this rule */
  channels: z.array(z.string()).nullable().default(null).optional(),
});

/**
 * Schema for alert rule response.
 */
export const alertRuleResponseSchema = z.object({
  /** Alert rule UUID */
  id: z.string(),
  /** Rule name */
  name: z.string(),
  /** Rule description */
  description: z.string().nullable().default(null),
  /** Whether the rule is active */
  enabled: z.boolean(),
  /** Severity level */
  severity: alertSeveritySchema,
  /** Risk score threshold */
  risk_threshold: z.number().int().nullable().default(null),
  /** Object types to match */
  object_types: z.array(z.string()).nullable().default(null),
  /** Camera IDs to apply to */
  camera_ids: z.array(z.string()).nullable().default(null),
  /** Zone IDs to match */
  zone_ids: z.array(z.string()).nullable().default(null),
  /** Minimum confidence */
  min_confidence: z.number().nullable().default(null),
  /** Time-based conditions */
  schedule: alertRuleScheduleSchema.nullable().default(null),
  /** Legacy conditions */
  conditions: alertRuleConditionsSchema.nullable().default(null),
  /** Template for dedup key */
  dedup_key_template: z.string(),
  /** Minimum seconds between duplicate alerts */
  cooldown_seconds: z.number().int(),
  /** Notification channels */
  channels: z.array(z.string()).default([]),
  /** Creation timestamp */
  created_at: z.string().datetime(),
  /** Last update timestamp */
  updated_at: z.string().datetime(),
});

/**
 * Schema for alert rule list response with pagination.
 */
export const alertRuleListResponseSchema = z.object({
  /** List of alert rules */
  items: z.array(alertRuleResponseSchema),
  /** Pagination metadata */
  pagination: z.unknown(),
});

/**
 * Schema for creating an alert.
 */
export const alertCreateSchema = z.object({
  /** Event ID that triggered this alert */
  event_id: z.number().int(),
  /** Alert rule UUID that matched (optional) */
  rule_id: z.string().nullable().default(null),
  /** Alert severity level */
  severity: alertSeveritySchema,
  /** Deduplication key for alert grouping. Only alphanumeric, underscore, hyphen, and colon characters allowed. */
  dedup_key: z.string().max(255),
  /** Notification channels to deliver to */
  channels: z.array(z.string()).default([]),
  /** Additional context for the alert */
  metadata: z.unknown().nullable().default(null),
});

/**
 * Schema for updating an alert (PATCH).
 */
export const alertUpdateSchema = z.object({
  /** Alert status */
  status: alertStatusSchema.nullable().default(null).optional(),
  /** Delivery timestamp */
  delivered_at: z.string().datetime().nullable().default(null).optional(),
  /** Notification channels that received this alert */
  channels: z.array(z.string()).nullable().default(null).optional(),
  /** Additional context for the alert */
  metadata: z.unknown().nullable().default(null).optional(),
});

/**
 * Schema for alert response.
 */
export const alertResponseSchema = z.object({
  /** Alert UUID */
  id: z.string(),
  /** Event ID that triggered this alert */
  event_id: z.number().int(),
  /** Alert rule UUID that matched */
  rule_id: z.string().nullable().default(null),
  /** Alert severity level */
  severity: alertSeveritySchema,
  /** Alert status */
  status: alertStatusSchema,
  /** Creation timestamp */
  created_at: z.string().datetime(),
  /** Last update timestamp */
  updated_at: z.string().datetime(),
  /** Delivery timestamp */
  delivered_at: z.string().datetime().nullable().default(null),
  /** Notification channels */
  channels: z.array(z.string()).default([]),
  /** Deduplication key */
  dedup_key: z.string(),
  /** Additional context */
  metadata: z.unknown().nullable().default(null),
});

/**
 * Schema for alert list response with pagination.
 */
export const alertListResponseSchema = z.object({
  /** List of alerts */
  items: z.array(alertResponseSchema),
  /** Pagination metadata */
  pagination: z.unknown(),
});

/**
 * Schema for checking alert deduplication.
 */
export const dedupCheckRequestSchema = z.object({
  /** Deduplication key to check. Only alphanumeric, underscore, hyphen, and colon characters allowed. */
  dedup_key: z.string().max(255),
  /** Cooldown window in seconds */
  cooldown_seconds: z.number().int().min(0).default(300),
});

/**
 * Schema for deduplication check response.
 */
export const dedupCheckResponseSchema = z.object({
  /** Whether a duplicate exists */
  is_duplicate: z.boolean(),
  /** ID of existing alert if duplicate */
  existing_alert_id: z.string().nullable().default(null),
  /** Seconds until cooldown expires (if duplicate) */
  seconds_until_cooldown_expires: z.number().int().nullable().default(null),
});

/**
 * Schema for testing a rule against historical events.
 */
export const ruleTestRequestSchema = z.object({
  /** Specific event IDs to test against. If not provided, tests against recent events. */
  event_ids: z.array(z.number().int()).nullable().default(null),
  /** Maximum number of recent events to test (if event_ids not provided) */
  limit: z.number().int().min(1).max(100).default(10),
  /** Override current time for schedule testing (ISO format) */
  test_time: z.string().datetime().nullable().default(null),
});

/**
 * Schema for a single event's test result.
 */
export const ruleTestEventResultSchema = z.object({
  /** Event ID */
  event_id: z.number().int(),
  /** Camera ID */
  camera_id: z.string(),
  /** Event risk score */
  risk_score: z.number().int().nullable().default(null),
  /** Detected object types */
  object_types: z.array(z.string()).default([]),
  /** Whether the rule matched this event */
  matches: z.boolean(),
  /** List of conditions that matched */
  matched_conditions: z.array(z.string()).default([]),
  /** Event start timestamp */
  started_at: z.string().nullable().default(null),
});

/**
 * Schema for rule test response.
 */
export const ruleTestResponseSchema = z.object({
  /** Rule ID that was tested */
  rule_id: z.string(),
  /** Rule name */
  rule_name: z.string(),
  /** Number of events tested */
  events_tested: z.number().int(),
  /** Number of events that matched the rule */
  events_matched: z.number().int(),
  /** Proportion of events that matched (0.0-1.0) */
  match_rate: z.number(),
  /** Per-event test results */
  results: z.array(ruleTestEventResultSchema),
});

// =============================================================================
// Type Exports
// =============================================================================

/** Type for AlertRuleSchedule */
export type AlertRuleScheduleInput = z.input<typeof alertRuleScheduleSchema>;
export type AlertRuleScheduleOutput = z.output<typeof alertRuleScheduleSchema>;

/** Type for AlertRuleConditions */
export type AlertRuleConditionsInput = z.input<typeof alertRuleConditionsSchema>;
export type AlertRuleConditionsOutput = z.output<typeof alertRuleConditionsSchema>;

/** Type for AlertRuleCreate */
export type AlertRuleCreateInput = z.input<typeof alertRuleCreateSchema>;
export type AlertRuleCreateOutput = z.output<typeof alertRuleCreateSchema>;

/** Type for AlertRuleUpdate */
export type AlertRuleUpdateInput = z.input<typeof alertRuleUpdateSchema>;
export type AlertRuleUpdateOutput = z.output<typeof alertRuleUpdateSchema>;

/** Type for AlertRuleResponse */
export type AlertRuleResponseInput = z.input<typeof alertRuleResponseSchema>;
export type AlertRuleResponseOutput = z.output<typeof alertRuleResponseSchema>;

/** Type for AlertRuleListResponse */
export type AlertRuleListResponseInput = z.input<typeof alertRuleListResponseSchema>;
export type AlertRuleListResponseOutput = z.output<typeof alertRuleListResponseSchema>;

/** Type for AlertCreate */
export type AlertCreateInput = z.input<typeof alertCreateSchema>;
export type AlertCreateOutput = z.output<typeof alertCreateSchema>;

/** Type for AlertUpdate */
export type AlertUpdateInput = z.input<typeof alertUpdateSchema>;
export type AlertUpdateOutput = z.output<typeof alertUpdateSchema>;

/** Type for AlertResponse */
export type AlertResponseInput = z.input<typeof alertResponseSchema>;
export type AlertResponseOutput = z.output<typeof alertResponseSchema>;

/** Type for AlertListResponse */
export type AlertListResponseInput = z.input<typeof alertListResponseSchema>;
export type AlertListResponseOutput = z.output<typeof alertListResponseSchema>;

/** Type for DedupCheckRequest */
export type DedupCheckRequestInput = z.input<typeof dedupCheckRequestSchema>;
export type DedupCheckRequestOutput = z.output<typeof dedupCheckRequestSchema>;

/** Type for DedupCheckResponse */
export type DedupCheckResponseInput = z.input<typeof dedupCheckResponseSchema>;
export type DedupCheckResponseOutput = z.output<typeof dedupCheckResponseSchema>;

/** Type for RuleTestRequest */
export type RuleTestRequestInput = z.input<typeof ruleTestRequestSchema>;
export type RuleTestRequestOutput = z.output<typeof ruleTestRequestSchema>;

/** Type for RuleTestEventResult */
export type RuleTestEventResultInput = z.input<typeof ruleTestEventResultSchema>;
export type RuleTestEventResultOutput = z.output<typeof ruleTestEventResultSchema>;

/** Type for RuleTestResponse */
export type RuleTestResponseInput = z.input<typeof ruleTestResponseSchema>;
export type RuleTestResponseOutput = z.output<typeof ruleTestResponseSchema>;
