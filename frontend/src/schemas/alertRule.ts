/**
 * Zod validation schemas for AlertRule forms.
 *
 * These schemas mirror the backend Pydantic schemas in:
 * - backend/api/schemas/alerts.py
 *
 * IMPORTANT: When modifying these schemas, ensure they match the backend.
 * Backend validation is authoritative; frontend validation provides UX feedback.
 */

import { z } from 'zod';

// =============================================================================
// Constants (aligned with backend Pydantic Field constraints)
// =============================================================================

/** Alert rule name constraints from backend AlertRuleCreate schema */
export const ALERT_RULE_NAME_CONSTRAINTS = {
  minLength: 1,
  maxLength: 255,
} as const;

/** Risk threshold constraints from backend (ge=0, le=100) */
export const RISK_THRESHOLD_CONSTRAINTS = {
  min: 0,
  max: 100,
} as const;

/** Min confidence constraints from backend (ge=0.0, le=1.0) */
export const MIN_CONFIDENCE_CONSTRAINTS = {
  min: 0,
  max: 1,
} as const;

/** Cooldown seconds constraints from backend (ge=0) */
export const COOLDOWN_SECONDS_CONSTRAINTS = {
  min: 0,
} as const;

/** Dedup key template constraints from backend (max_length=255) */
export const DEDUP_KEY_TEMPLATE_CONSTRAINTS = {
  maxLength: 255,
} as const;

/**
 * Alert severity enum values from backend AlertSeverity enum.
 * See: backend/api/schemas/alerts.py
 */
export const ALERT_SEVERITY_VALUES = ['low', 'medium', 'high', 'critical'] as const;

/** Type derived from alert severity values */
export type AlertSeverityValue = (typeof ALERT_SEVERITY_VALUES)[number];

/**
 * Valid days of week from backend VALID_DAYS.
 * See: backend/api/schemas/alerts.py
 */
export const VALID_DAYS = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

/** Type derived from valid days */
export type DayOfWeekValue = (typeof VALID_DAYS)[number];

// =============================================================================
// Time Format Validation (aligned with backend validate_time_format)
// =============================================================================

/**
 * Time format regex pattern from backend schema.
 * Backend: pattern=r"^\d{2}:\d{2}$"
 */
const TIME_FORMAT_PATTERN = /^\d{2}:\d{2}$/;

/**
 * Validates time format and values.
 * Matches backend validate_time_format() in alerts.py
 *
 * @param timeStr - Time string in HH:MM format
 * @returns Error message if invalid, true if valid
 */
function validateTimeFormat(timeStr: string): string | true {
  // Check basic format: must be exactly 5 chars with colon at position 2
  if (!timeStr || timeStr.length !== 5 || timeStr[2] !== ':') {
    return `Invalid time format '${timeStr}'. Expected HH:MM format.`;
  }

  // Check that it matches the regex pattern
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

// =============================================================================
// Zod Schemas
// =============================================================================

/**
 * Alert severity schema - matches backend AlertSeverity enum.
 */
export const alertSeveritySchema = z.enum(ALERT_SEVERITY_VALUES, {
  error: 'Invalid alert severity. Must be: low, medium, high, or critical',
});

/**
 * Day of week schema - matches backend VALID_DAYS.
 */
export const dayOfWeekSchema = z.enum(VALID_DAYS, {
  error: `Invalid day. Must be one of: ${VALID_DAYS.join(', ')}`,
});

/**
 * Alert rule name schema - matches backend AlertRuleCreate.name field.
 * Backend constraint: min_length=1, max_length=255
 */
export const alertRuleNameSchema = z
  .string()
  .min(ALERT_RULE_NAME_CONSTRAINTS.minLength, { message: 'Name is required' })
  .max(ALERT_RULE_NAME_CONSTRAINTS.maxLength, {
    message: `Name must be at most ${ALERT_RULE_NAME_CONSTRAINTS.maxLength} characters`,
  })
  .transform((val) => val.trim())
  .refine((val) => val.length >= ALERT_RULE_NAME_CONSTRAINTS.minLength, {
    message: 'Name is required',
  });

/**
 * Risk threshold schema - matches backend AlertRuleCreate.risk_threshold field.
 * Backend constraint: ge=0, le=100
 */
export const riskThresholdSchema = z
  .number()
  .int({ message: 'Risk threshold must be a whole number' })
  .min(RISK_THRESHOLD_CONSTRAINTS.min, {
    message: `Risk threshold must be at least ${RISK_THRESHOLD_CONSTRAINTS.min}`,
  })
  .max(RISK_THRESHOLD_CONSTRAINTS.max, {
    message: `Risk threshold must be at most ${RISK_THRESHOLD_CONSTRAINTS.max}`,
  })
  .nullable()
  .optional();

/**
 * Min confidence schema - matches backend AlertRuleCreate.min_confidence field.
 * Backend constraint: ge=0.0, le=1.0
 */
export const minConfidenceSchema = z
  .number()
  .min(MIN_CONFIDENCE_CONSTRAINTS.min, {
    message: `Confidence must be at least ${MIN_CONFIDENCE_CONSTRAINTS.min}`,
  })
  .max(MIN_CONFIDENCE_CONSTRAINTS.max, {
    message: `Confidence must be at most ${MIN_CONFIDENCE_CONSTRAINTS.max}`,
  })
  .nullable()
  .optional();

/**
 * Cooldown seconds schema - matches backend AlertRuleCreate.cooldown_seconds field.
 * Backend constraint: ge=0
 */
export const cooldownSecondsSchema = z
  .number()
  .int({ message: 'Cooldown must be a whole number' })
  .min(COOLDOWN_SECONDS_CONSTRAINTS.min, { message: 'Cooldown cannot be negative' });

/**
 * Dedup key template schema - matches backend AlertRuleCreate.dedup_key_template field.
 * Backend constraint: max_length=255
 */
export const dedupKeyTemplateSchema = z
  .string()
  .max(DEDUP_KEY_TEMPLATE_CONSTRAINTS.maxLength, {
    message: `Dedup key template must be at most ${DEDUP_KEY_TEMPLATE_CONSTRAINTS.maxLength} characters`,
  });

/**
 * Time string schema - matches backend AlertRuleSchedule.start_time/end_time fields.
 * Backend constraint: pattern=r"^\d{2}:\d{2}$" with hours 00-23, minutes 00-59
 */
export const timeStringSchema = z
  .string()
  .superRefine((val, ctx) => {
    const result = validateTimeFormat(val);
    if (result !== true) {
      ctx.addIssue({
        code: 'custom',
        message: result,
      });
    }
  })
  .nullable()
  .optional();

/**
 * Days array schema - matches backend AlertRuleSchedule.days field.
 * Backend validates that all days are valid day names (monday-sunday).
 */
export const daysArraySchema = z
  .array(dayOfWeekSchema)
  .nullable()
  .optional()
  .transform((val) => {
    // Normalize to lowercase (backend does this too)
    return val?.map((day) => day.toLowerCase() as DayOfWeekValue) ?? null;
  });

/**
 * Alert rule schedule schema - matches backend AlertRuleSchedule model.
 */
export const alertRuleScheduleSchema = z
  .object({
    days: daysArraySchema,
    start_time: timeStringSchema,
    end_time: timeStringSchema,
    timezone: z.string().default('UTC'),
  })
  .nullable()
  .optional();

/**
 * Schema for creating a new alert rule.
 * Matches backend AlertRuleCreate Pydantic model.
 */
export const alertRuleCreateSchema = z.object({
  name: alertRuleNameSchema,
  description: z.string().nullable().optional(),
  enabled: z.boolean().default(true),
  severity: alertSeveritySchema.default('medium'),
  risk_threshold: riskThresholdSchema,
  object_types: z.array(z.string()).nullable().optional(),
  camera_ids: z.array(z.string()).nullable().optional(),
  zone_ids: z.array(z.string()).nullable().optional(),
  min_confidence: minConfidenceSchema,
  schedule: alertRuleScheduleSchema,
  dedup_key_template: dedupKeyTemplateSchema.default('{camera_id}:{rule_id}'),
  cooldown_seconds: cooldownSecondsSchema.default(300),
  channels: z.array(z.string()).default([]),
});

/**
 * Schema for updating an existing alert rule.
 * Matches backend AlertRuleUpdate Pydantic model.
 * All fields are optional for partial updates.
 */
export const alertRuleUpdateSchema = z.object({
  name: alertRuleNameSchema.optional(),
  description: z.string().nullable().optional(),
  enabled: z.boolean().optional(),
  severity: alertSeveritySchema.optional(),
  risk_threshold: riskThresholdSchema,
  object_types: z.array(z.string()).nullable().optional(),
  camera_ids: z.array(z.string()).nullable().optional(),
  zone_ids: z.array(z.string()).nullable().optional(),
  min_confidence: minConfidenceSchema,
  schedule: alertRuleScheduleSchema,
  dedup_key_template: dedupKeyTemplateSchema.optional(),
  cooldown_seconds: cooldownSecondsSchema.optional(),
  channels: z.array(z.string()).nullable().optional(),
});

/**
 * Schema for the alert rule form (used in AlertRuleForm component).
 * Converts nullable fields to form-friendly types.
 */
export const alertRuleFormSchema = z.object({
  name: alertRuleNameSchema,
  description: z.string().default(''),
  enabled: z.boolean().default(true),
  severity: alertSeveritySchema.default('medium'),
  risk_threshold: z
    .union([z.number().int().min(0).max(100), z.literal('')])
    .nullable()
    .transform((val) => (val === '' ? null : val)),
  object_types: z.array(z.string()).default([]),
  camera_ids: z.array(z.string()).default([]),
  zone_ids: z.array(z.string()).default([]),
  min_confidence: z
    .union([z.number().min(0).max(1), z.literal('')])
    .nullable()
    .transform((val) => (val === '' ? null : val)),
  schedule_enabled: z.boolean().default(false),
  schedule_days: z.array(dayOfWeekSchema).default([]),
  schedule_start_time: z.string().default('22:00'),
  schedule_end_time: z.string().default('06:00'),
  schedule_timezone: z.string().default('UTC'),
  cooldown_seconds: cooldownSecondsSchema.default(300),
  channels: z.array(z.string()).default([]),
});

// =============================================================================
// Type Exports
// =============================================================================

/** Type for AlertRuleCreate payload */
export type AlertRuleCreateInput = z.input<typeof alertRuleCreateSchema>;
export type AlertRuleCreateOutput = z.output<typeof alertRuleCreateSchema>;

/** Type for AlertRuleUpdate payload */
export type AlertRuleUpdateInput = z.input<typeof alertRuleUpdateSchema>;
export type AlertRuleUpdateOutput = z.output<typeof alertRuleUpdateSchema>;

/** Type for alert rule form data */
export type AlertRuleFormInput = z.input<typeof alertRuleFormSchema>;
export type AlertRuleFormOutput = z.output<typeof alertRuleFormSchema>;

/** Type for alert rule schedule */
export type AlertRuleScheduleInput = z.input<typeof alertRuleScheduleSchema>;
export type AlertRuleScheduleOutput = z.output<typeof alertRuleScheduleSchema>;
