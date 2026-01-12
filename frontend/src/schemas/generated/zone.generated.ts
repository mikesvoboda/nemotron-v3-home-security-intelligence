/**
 * Generated Zod schemas for zone.py
 *
 * AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
 * Run: uv run python scripts/generate_zod_schemas.py
 *
 * Source: backend/api/schemas/zone.py
 */

import { z } from 'zod';

// =============================================================================
// Enum Schemas
// =============================================================================

/** ZoneShape enum values */
export const ZONE_SHAPE_VALUES = ['rectangle', 'polygon'] as const;

/** ZoneShape Zod schema */
export const zoneShapeSchema = z.enum(ZONE_SHAPE_VALUES);

/** ZoneShape type */
export type ZoneShapeValue = (typeof ZONE_SHAPE_VALUES)[number];

/** ZoneType enum values */
export const ZONE_TYPE_VALUES = ['entry_point', 'driveway', 'sidewalk', 'yard', 'other'] as const;

/** ZoneType Zod schema */
export const zoneTypeSchema = z.enum(ZONE_TYPE_VALUES);

/** ZoneType type */
export type ZoneTypeValue = (typeof ZONE_TYPE_VALUES)[number];

// =============================================================================
// Schema Definitions
// =============================================================================

/**
 * Schema for creating a new zone.
 */
export const zoneCreateSchema = z.object({
  /** Zone name */
  name: z.string().min(1).max(255),
  /** Type of zone */
  zone_type: zoneTypeSchema,
  /** Array of normalized [x, y] points (0-1 range) */
  coordinates: z.array(z.array(z.number())),
  /** Shape of the zone */
  shape: zoneShapeSchema,
  /** Hex color for UI display */
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default('#3B82F6'),
  /** Whether zone is active */
  enabled: z.boolean().default(true),
  /** Priority for overlapping zones (higher = more important) */
  priority: z.number().int().min(0).max(100).default(0),
});

/**
 * Schema for updating an existing zone.
 */
export const zoneUpdateSchema = z.object({
  /** Zone name */
  name: z.string().min(1).max(255).nullable().default(null).optional(),
  /** Type of zone */
  zone_type: zoneTypeSchema.nullable().default(null).optional(),
  /** Array of normalized [x, y] points (0-1 range) */
  coordinates: z.array(z.array(z.number())).nullable().default(null).optional(),
  /** Shape of the zone */
  shape: zoneShapeSchema.nullable().default(null).optional(),
  /** Hex color for UI display */
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).nullable().default(null).optional(),
  /** Whether zone is active */
  enabled: z.boolean().nullable().default(null).optional(),
  /** Priority for overlapping zones (higher = more important) */
  priority: z.number().int().min(0).max(100).nullable().default(null).optional(),
});

/**
 * Schema for zone response.
 */
export const zoneResponseSchema = z.object({
  /** Zone UUID */
  id: z.string(),
  /** Camera ID this zone belongs to */
  camera_id: z.string(),
  /** Zone name */
  name: z.string(),
  /** Type of zone */
  zone_type: zoneTypeSchema,
  /** Array of normalized [x, y] points (0-1 range) */
  coordinates: z.array(z.array(z.number())),
  /** Shape of the zone */
  shape: zoneShapeSchema,
  /** Hex color for UI display */
  color: z.string(),
  /** Whether zone is active */
  enabled: z.boolean(),
  /** Priority for overlapping zones */
  priority: z.number().int(),
  /** Timestamp when zone was created */
  created_at: z.string().datetime(),
  /** Timestamp when zone was last updated */
  updated_at: z.string().datetime(),
});

/**
 * Schema for zone list response.
 */
export const zoneListResponseSchema = z.object({
  /** List of zones */
  items: z.array(zoneResponseSchema),
  /** Pagination metadata */
  pagination: z.unknown(),
});

// =============================================================================
// Type Exports
// =============================================================================

/** Type for ZoneCreate */
export type ZoneCreateInput = z.input<typeof zoneCreateSchema>;
export type ZoneCreateOutput = z.output<typeof zoneCreateSchema>;

/** Type for ZoneUpdate */
export type ZoneUpdateInput = z.input<typeof zoneUpdateSchema>;
export type ZoneUpdateOutput = z.output<typeof zoneUpdateSchema>;

/** Type for ZoneResponse */
export type ZoneResponseInput = z.input<typeof zoneResponseSchema>;
export type ZoneResponseOutput = z.output<typeof zoneResponseSchema>;

/** Type for ZoneListResponse */
export type ZoneListResponseInput = z.input<typeof zoneListResponseSchema>;
export type ZoneListResponseOutput = z.output<typeof zoneListResponseSchema>;
