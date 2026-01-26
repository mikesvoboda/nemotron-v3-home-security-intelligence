/**
 * Zod validation schemas for AlertForm (legacy form component).
 *
 * These schemas mirror the backend Pydantic schemas in:
 * - backend/api/schemas/alerts.py
 *
 * Note: This is for the legacy AlertForm component. For AlertRuleForm,
 * use the schemas in alertRule.ts.
 *
 * IMPORTANT: When modifying these schemas, ensure they match the backend.
 * Backend validation is authoritative; frontend validation provides UX feedback.
 *
 * @see NEM-3820 Migrate AlertForm to useForm with Zod
 */

import { z } from 'zod';

// =============================================================================
// Constants (aligned with backend Pydantic Field constraints)
// =============================================================================

/** Alert rule name constraints from backend AlertRuleCreate schema */
export const ALERT_FORM_NAME_CONSTRAINTS = {
  minLength: 1,
  maxLength: 255,
} as const;

/** Risk threshold constraints from backend (ge=0, le=100) */
export const ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS = {
  min: 0,
  max: 100,
} as const;

/** Min confidence constraints from backend (ge=0.0, le=1.0) */
export const ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS = {
  min: 0,
  max: 1,
} as const;

/** Cooldown seconds constraints from backend (ge=0) */
export const ALERT_FORM_COOLDOWN_SECONDS_CONSTRAINTS = {
  min: 0,
} as const;

/**
 * Alert severity enum values from backend AlertSeverity enum.
 */
export const ALERT_FORM_SEVERITY_VALUES = ['low', 'medium', 'high', 'critical'] as const;

/** Type derived from alert severity values */
export type AlertFormSeverityValue = (typeof ALERT_FORM_SEVERITY_VALUES)[number];

/**
 * Valid days of week from backend VALID_DAYS.
 */
export const ALERT_FORM_VALID_DAYS = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

/** Type derived from valid days */
export type AlertFormDayOfWeekValue = (typeof ALERT_FORM_VALID_DAYS)[number];

// =============================================================================
// Zod Schemas
// =============================================================================

/**
 * Alert severity schema - matches backend AlertSeverity enum.
 */
export const alertFormSeveritySchema = z.enum(ALERT_FORM_SEVERITY_VALUES, {
  error: 'Invalid alert severity. Must be: low, medium, high, or critical',
});

/**
 * Day of week schema - matches backend VALID_DAYS.
 */
export const alertFormDayOfWeekSchema = z.enum(ALERT_FORM_VALID_DAYS, {
  error: `Invalid day. Must be one of: ${ALERT_FORM_VALID_DAYS.join(', ')}`,
});

/**
 * Alert form name schema - matches backend AlertRuleCreate.name field.
 * Backend constraint: min_length=1, max_length=255
 */
export const alertFormNameSchema = z
  .string()
  .min(ALERT_FORM_NAME_CONSTRAINTS.minLength, { message: 'Name is required' })
  .max(ALERT_FORM_NAME_CONSTRAINTS.maxLength, {
    message: `Name must be at most ${ALERT_FORM_NAME_CONSTRAINTS.maxLength} characters`,
  })
  .transform((val) => val.trim())
  .refine((val) => val.length >= ALERT_FORM_NAME_CONSTRAINTS.minLength, {
    message: 'Name is required',
  });

/**
 * Risk threshold schema for AlertForm.
 * Backend constraint: ge=0, le=100
 */
export const alertFormRiskThresholdSchema = z
  .union([
    z
      .number()
      .int({ message: 'Risk threshold must be a whole number' })
      .min(ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.min, {
        message: `Risk threshold must be at least ${ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.min}`,
      })
      .max(ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.max, {
        message: `Risk threshold must be at most ${ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.max}`,
      }),
    z.literal(''),
  ])
  .nullable()
  .transform((val) => (val === '' ? null : val));

/**
 * Min confidence schema for AlertForm.
 * Backend constraint: ge=0.0, le=1.0
 */
export const alertFormMinConfidenceSchema = z
  .union([
    z
      .number()
      .min(ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.min, {
        message: `Confidence must be at least ${ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.min}`,
      })
      .max(ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.max, {
        message: `Confidence must be at most ${ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.max}`,
      }),
    z.literal(''),
  ])
  .nullable()
  .transform((val) => (val === '' ? null : val));

/**
 * Cooldown seconds schema for AlertForm.
 * Backend constraint: ge=0
 */
export const alertFormCooldownSecondsSchema = z
  .number()
  .int({ message: 'Cooldown must be a whole number' })
  .min(ALERT_FORM_COOLDOWN_SECONDS_CONSTRAINTS.min, { message: 'Cooldown cannot be negative' });

/**
 * Schema for the AlertForm component.
 * Matches the legacy AlertForm data structure.
 */
export const alertFormSchema = z.object({
  name: alertFormNameSchema,
  description: z.string().default('').transform((val) => val.trim()),
  enabled: z.boolean().default(true),
  severity: alertFormSeveritySchema.default('medium'),
  risk_threshold: alertFormRiskThresholdSchema.default(null),
  object_types: z.array(z.string()).default([]),
  camera_ids: z.array(z.string()).default([]),
  min_confidence: alertFormMinConfidenceSchema.default(null),
  schedule_enabled: z.boolean().default(false),
  schedule_days: z.array(alertFormDayOfWeekSchema).default([]),
  schedule_start_time: z.string().default('22:00'),
  schedule_end_time: z.string().default('06:00'),
  schedule_timezone: z.string().default('UTC'),
  cooldown_seconds: alertFormCooldownSecondsSchema.default(300),
  channels: z.array(z.string()).default([]),
});

// =============================================================================
// Type Exports
// =============================================================================

/** Type for AlertForm input (before transformation) */
export type AlertFormInput = z.input<typeof alertFormSchema>;

/** Type for AlertForm output (after transformation) */
export type AlertFormOutput = z.output<typeof alertFormSchema>;
