/**
 * Reusable Zod Schema Primitives
 *
 * This module provides a library of reusable schema primitives that ensure
 * consistency across all Zod schemas in the application. These primitives
 * are used for both frontend form validation and API response parsing.
 *
 * Benefits:
 * - Single source of truth for common validation patterns
 * - Consistent error messages across the application
 * - Type-safe with inferred TypeScript types
 * - Reduces code duplication
 *
 * @example
 * ```typescript
 * import { cameraId, riskScore, riskLevel, timestamp } from '@/schemas/primitives';
 *
 * const eventSchema = z.object({
 *   camera_id: cameraId,
 *   risk_score: riskScore,
 *   risk_level: riskLevel,
 *   started_at: timestamp
 * });
 * ```
 */

import { z } from 'zod';

// =============================================================================
// ID Primitives
// =============================================================================

/**
 * UUID schema for entity identifiers.
 * Validates that the string is a valid UUID v4 format.
 */
export const uuid = z.string().uuid({ error: 'Invalid UUID format' });

/**
 * Camera ID - UUID string identifying a camera.
 */
export const cameraId = z.string().uuid({ error: 'Invalid camera ID format' });

/**
 * Event ID - UUID string identifying a security event.
 */
export const eventId = z.string().uuid({ error: 'Invalid event ID format' });

/**
 * Detection ID - UUID string identifying a detection within an event.
 */
export const detectionId = z.string().uuid({ error: 'Invalid detection ID format' });

/**
 * Zone ID - UUID string identifying a monitoring zone.
 */
export const zoneId = z.string().uuid({ error: 'Invalid zone ID format' });

/**
 * Alert Rule ID - UUID string identifying an alert rule.
 */
export const alertRuleId = z.string().uuid({ error: 'Invalid alert rule ID format' });

/**
 * Entity ID - UUID string identifying a tracked entity (person/vehicle).
 */
export const entityId = z.string().uuid({ error: 'Invalid entity ID format' });

/**
 * Batch ID - UUID string identifying a processing batch.
 */
export const batchId = z.string().uuid({ error: 'Invalid batch ID format' });

// =============================================================================
// Risk Assessment Primitives
// =============================================================================

/**
 * Risk score constraints (matches backend RiskAnalysis model).
 * Range: 0-100, integer values only.
 */
export const RISK_SCORE_CONSTRAINTS = {
  min: 0,
  max: 100,
} as const;

/**
 * Risk score schema - integer from 0 to 100.
 * Used for LLM-determined threat scores.
 */
export const riskScore = z
  .number()
  .int({ error: 'Risk score must be a whole number' })
  .min(RISK_SCORE_CONSTRAINTS.min, { error: `Risk score must be at least ${RISK_SCORE_CONSTRAINTS.min}` })
  .max(RISK_SCORE_CONSTRAINTS.max, { error: `Risk score must be at most ${RISK_SCORE_CONSTRAINTS.max}` });

/**
 * Optional risk score - for fields that may not have a score yet.
 */
export const optionalRiskScore = riskScore.nullable().optional();

/**
 * Risk level values from backend RiskLevel enum.
 */
export const RISK_LEVEL_VALUES = ['low', 'medium', 'high', 'critical'] as const;

/**
 * Risk level type derived from values.
 */
export type RiskLevelValue = (typeof RISK_LEVEL_VALUES)[number];

/**
 * Risk level schema - categorical risk classification.
 */
export const riskLevel = z.enum(RISK_LEVEL_VALUES, {
  error: 'Invalid risk level. Must be: low, medium, high, or critical',
});

/**
 * Optional risk level - for fields that may not have a level yet.
 */
export const optionalRiskLevel = riskLevel.nullable().optional();

// =============================================================================
// Confidence Primitives
// =============================================================================

/**
 * Confidence constraints (0.0 to 1.0).
 */
export const CONFIDENCE_CONSTRAINTS = {
  min: 0,
  max: 1,
} as const;

/**
 * Confidence score schema - float from 0 to 1.
 * Used for detection confidence values.
 */
export const confidence = z
  .number()
  .min(CONFIDENCE_CONSTRAINTS.min, { error: `Confidence must be at least ${CONFIDENCE_CONSTRAINTS.min}` })
  .max(CONFIDENCE_CONSTRAINTS.max, { error: `Confidence must be at most ${CONFIDENCE_CONSTRAINTS.max}` });

/**
 * Optional confidence - for fields that may not have confidence yet.
 */
export const optionalConfidence = confidence.nullable().optional();

// =============================================================================
// Timestamp Primitives
// =============================================================================

/**
 * Timestamp schema - coerces various inputs to Date objects.
 * Accepts: Date objects, ISO date strings, Unix timestamps.
 */
export const timestamp = z.coerce.date({ error: 'Invalid timestamp format' });

/**
 * Optional timestamp - for nullable timestamp fields.
 */
export const optionalTimestamp = timestamp.nullable().optional();

/**
 * ISO date string schema - validates ISO 8601 format.
 */
export const isoDateString = z.string().datetime({ error: 'Invalid ISO date string format' });

/**
 * Optional ISO date string.
 */
export const optionalIsoDateString = isoDateString.nullable().optional();

// =============================================================================
// Object Type Primitives
// =============================================================================

/**
 * Object type values from backend ObjectType enum.
 */
export const OBJECT_TYPE_VALUES = ['person', 'vehicle', 'animal', 'package'] as const;

/**
 * Object type derived from values.
 */
export type ObjectTypeValue = (typeof OBJECT_TYPE_VALUES)[number];

/**
 * Object type schema - detection class type.
 */
export const objectType = z.enum(OBJECT_TYPE_VALUES, {
  error: 'Invalid object type. Must be: person, vehicle, animal, or package',
});

/**
 * Array of object types.
 */
export const objectTypes = z.array(objectType);

/**
 * Optional object types array.
 */
export const optionalObjectTypes = objectTypes.nullable().optional();

// =============================================================================
// Camera Status Primitives
// =============================================================================

/**
 * Camera status values from backend CameraStatus enum.
 */
export const CAMERA_STATUS_VALUES = ['online', 'offline', 'error', 'unknown'] as const;

/**
 * Camera status type derived from values.
 */
export type CameraStatusValue = (typeof CAMERA_STATUS_VALUES)[number];

/**
 * Camera status schema.
 */
export const cameraStatus = z.enum(CAMERA_STATUS_VALUES, {
  error: 'Invalid camera status. Must be: online, offline, error, or unknown',
});

// =============================================================================
// Alert Severity Primitives
// =============================================================================

/**
 * Alert severity values from backend AlertSeverity enum.
 */
export const ALERT_SEVERITY_VALUES = ['low', 'medium', 'high', 'critical'] as const;

/**
 * Alert severity type derived from values.
 */
export type AlertSeverityValue = (typeof ALERT_SEVERITY_VALUES)[number];

/**
 * Alert severity schema.
 */
export const alertSeverity = z.enum(ALERT_SEVERITY_VALUES, {
  error: 'Invalid alert severity. Must be: low, medium, high, or critical',
});

// =============================================================================
// Day of Week Primitives
// =============================================================================

/**
 * Valid days of week for schedules.
 */
export const DAY_OF_WEEK_VALUES = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

/**
 * Day of week type derived from values.
 */
export type DayOfWeekValue = (typeof DAY_OF_WEEK_VALUES)[number];

/**
 * Day of week schema.
 */
export const dayOfWeek = z.enum(DAY_OF_WEEK_VALUES, {
  error: `Invalid day. Must be one of: ${DAY_OF_WEEK_VALUES.join(', ')}`,
});

/**
 * Array of days of week.
 */
export const daysOfWeek = z.array(dayOfWeek);

// =============================================================================
// String Primitives with Constraints
// =============================================================================

/**
 * Non-empty string schema.
 */
export const nonEmptyString = z.string().min(1, { error: 'This field is required' });

/**
 * Creates a string schema with min/max length constraints.
 *
 * @param constraints - Object with minLength and maxLength
 * @param fieldName - Field name for error messages
 * @returns Zod string schema with constraints
 */
export function stringWithLength(
  constraints: { minLength?: number; maxLength?: number },
  fieldName: string
): z.ZodString {
  let schema = z.string();

  if (constraints.minLength !== undefined && constraints.minLength > 0) {
    schema = schema.min(constraints.minLength, {
      error: constraints.minLength === 1 ? `${fieldName} is required` : `${fieldName} must be at least ${constraints.minLength} characters`,
    });
  }

  if (constraints.maxLength !== undefined) {
    schema = schema.max(constraints.maxLength, {
      error: `${fieldName} must be at most ${constraints.maxLength} characters`,
    });
  }

  return schema;
}

// =============================================================================
// Bounding Box Primitives
// =============================================================================

/**
 * Coordinate value (0 to 1 normalized).
 */
export const normalizedCoordinate = z.number().min(0).max(1);

/**
 * Bounding box schema - normalized coordinates [x1, y1, x2, y2].
 */
export const boundingBox = z.tuple([
  normalizedCoordinate,
  normalizedCoordinate,
  normalizedCoordinate,
  normalizedCoordinate,
]);

/**
 * Optional bounding box.
 */
export const optionalBoundingBox = boundingBox.nullable().optional();

// =============================================================================
// Pagination Primitives
// =============================================================================

/**
 * Pagination page number (1-indexed).
 */
export const pageNumber = z.number().int().min(1, { error: 'Page number must be at least 1' });

/**
 * Pagination page size.
 */
export const pageSize = z.number().int().min(1).max(100, { error: 'Page size must be between 1 and 100' });

/**
 * Total count for pagination.
 */
export const totalCount = z.number().int().min(0);

/**
 * Cursor for cursor-based pagination.
 */
export const paginationCursor = z.string().nullable().optional();

// =============================================================================
// Time String Primitives
// =============================================================================

/**
 * Time format regex pattern (HH:MM).
 */
const TIME_FORMAT_PATTERN = /^\d{2}:\d{2}$/;

/**
 * Validates time format and values.
 * Matches backend validate_time_format() in alerts.py
 */
function validateTimeFormat(timeStr: string): string | true {
  if (!timeStr || timeStr.length !== 5 || timeStr[2] !== ':') {
    return `Invalid time format '${timeStr}'. Expected HH:MM format.`;
  }

  if (!TIME_FORMAT_PATTERN.test(timeStr)) {
    return `Invalid time format '${timeStr}'. Hours and minutes must be numeric.`;
  }

  const hours = parseInt(timeStr.substring(0, 2), 10);
  const minutes = parseInt(timeStr.substring(3, 5), 10);

  if (isNaN(hours) || isNaN(minutes)) {
    return `Invalid time format '${timeStr}'. Hours and minutes must be numeric.`;
  }

  if (hours < 0 || hours > 23) {
    return `Invalid hours '${hours}' in time '${timeStr}'. Hours must be 00-23.`;
  }

  if (minutes < 0 || minutes > 59) {
    return `Invalid minutes '${minutes}' in time '${timeStr}'. Minutes must be 00-59.`;
  }

  return true;
}

/**
 * Time string schema - validates HH:MM format.
 */
export const timeString = z
  .string()
  .superRefine((val, ctx) => {
    const result = validateTimeFormat(val);
    if (result !== true) {
      ctx.addIssue({
        code: 'custom',
        message: result,
      });
    }
  });

/**
 * Optional time string.
 */
export const optionalTimeString = timeString.nullable().optional();

// =============================================================================
// Type Exports (derived from schemas)
// =============================================================================

/** Type for UUID */
export type UUID = z.infer<typeof uuid>;

/** Type for camera ID */
export type CameraIdType = z.infer<typeof cameraId>;

/** Type for event ID */
export type EventIdType = z.infer<typeof eventId>;

/** Type for risk score */
export type RiskScoreType = z.infer<typeof riskScore>;

/** Type for confidence */
export type ConfidenceType = z.infer<typeof confidence>;

/** Type for timestamp */
export type TimestampType = z.infer<typeof timestamp>;

/** Type for bounding box */
export type BoundingBoxType = z.infer<typeof boundingBox>;
