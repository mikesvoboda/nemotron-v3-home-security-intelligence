/**
 * Zod validation schemas for Zone forms.
 *
 * These schemas mirror the backend Pydantic schemas in:
 * - backend/api/schemas/zone.py
 *
 * IMPORTANT: When modifying these schemas, ensure they match the backend.
 * Backend validation is authoritative; frontend validation provides UX feedback.
 */

import { z } from 'zod';

// =============================================================================
// Constants (aligned with backend Pydantic Field constraints)
// =============================================================================

/** Zone name constraints from backend ZoneCreate schema */
export const ZONE_NAME_CONSTRAINTS = {
  minLength: 1,
  maxLength: 255,
} as const;

/** Zone priority constraints from backend (ge=0, le=100) */
export const ZONE_PRIORITY_CONSTRAINTS = {
  min: 0,
  max: 100,
} as const;

/** Zone color pattern from backend (hex color format) */
export const ZONE_COLOR_PATTERN = /^#[0-9A-Fa-f]{6}$/;

/**
 * Zone type enum values from backend CameraZoneType enum.
 * See: backend/api/schemas/zone.py
 */
export const ZONE_TYPE_VALUES = ['entry_point', 'driveway', 'sidewalk', 'yard', 'other'] as const;

/** Type derived from zone type values */
export type ZoneTypeValue = (typeof ZONE_TYPE_VALUES)[number];

/**
 * Zone shape enum values from backend CameraZoneShape enum.
 * See: backend/api/schemas/zone.py
 */
export const ZONE_SHAPE_VALUES = ['rectangle', 'polygon'] as const;

/** Type derived from zone shape values */
export type ZoneShapeValue = (typeof ZONE_SHAPE_VALUES)[number];

// =============================================================================
// Zod Schemas
// =============================================================================

/**
 * Zone type schema - matches backend CameraZoneType enum.
 */
export const zoneTypeSchema = z.enum(ZONE_TYPE_VALUES, {
  error: `Invalid zone type. Must be: ${ZONE_TYPE_VALUES.join(', ')}`,
});

/**
 * Zone shape schema - matches backend CameraZoneShape enum.
 */
export const zoneShapeSchema = z.enum(ZONE_SHAPE_VALUES, {
  error: `Invalid zone shape. Must be: ${ZONE_SHAPE_VALUES.join(', ')}`,
});

/**
 * Zone name schema - matches backend ZoneCreate.name field.
 * Backend constraint: min_length=1, max_length=255
 */
export const zoneNameSchema = z
  .string()
  .min(ZONE_NAME_CONSTRAINTS.minLength, { message: 'Name is required' })
  .max(ZONE_NAME_CONSTRAINTS.maxLength, {
    message: `Name must be at most ${ZONE_NAME_CONSTRAINTS.maxLength} characters`,
  })
  .transform((val) => val.trim())
  .refine((val) => val.length >= ZONE_NAME_CONSTRAINTS.minLength, {
    message: 'Name is required',
  });

/**
 * Zone color schema - matches backend hex color pattern.
 * Backend constraint: pattern=r"^#[0-9A-Fa-f]{6}$"
 */
export const zoneColorSchema = z
  .string()
  .regex(ZONE_COLOR_PATTERN, { message: 'Color must be a valid hex color (e.g., #3B82F6)' });

/**
 * Zone priority schema - matches backend ZoneCreate.priority field.
 * Backend constraint: ge=0, le=100
 */
export const zonePrioritySchema = z
  .number()
  .int({ message: 'Priority must be a whole number' })
  .min(ZONE_PRIORITY_CONSTRAINTS.min, {
    message: `Priority must be at least ${ZONE_PRIORITY_CONSTRAINTS.min}`,
  })
  .max(ZONE_PRIORITY_CONSTRAINTS.max, {
    message: `Priority must be at most ${ZONE_PRIORITY_CONSTRAINTS.max}`,
  });

/**
 * Schema for the zone form (used in ZoneForm component).
 * Matches backend ZoneCreate Pydantic model.
 */
export const zoneFormSchema = z.object({
  name: zoneNameSchema,
  zone_type: zoneTypeSchema.default('other'),
  shape: zoneShapeSchema.default('rectangle'),
  color: zoneColorSchema.default('#3B82F6'),
  enabled: z.boolean().default(true),
  priority: zonePrioritySchema.default(0),
});

// =============================================================================
// Type Exports
// =============================================================================

/** Type for zone form input (before transformation) */
export type ZoneFormInput = z.input<typeof zoneFormSchema>;

/** Type for zone form output (after transformation) */
export type ZoneFormOutput = z.output<typeof zoneFormSchema>;
