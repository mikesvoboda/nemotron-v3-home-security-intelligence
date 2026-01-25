/**
 * Zod validation schemas for Camera forms.
 *
 * These schemas mirror the backend Pydantic schemas in:
 * - backend/api/schemas/camera.py
 *
 * IMPORTANT: When modifying these schemas, ensure they match the backend.
 * Backend validation is authoritative; frontend validation provides UX feedback.
 */

import { z } from 'zod';

// =============================================================================
// Constants (aligned with backend Pydantic Field constraints)
// =============================================================================

/** Camera name constraints from backend CameraCreate/CameraUpdate schemas */
export const CAMERA_NAME_CONSTRAINTS = {
  minLength: 1,
  maxLength: 255,
} as const;

/** Camera folder path constraints from backend CameraCreate/CameraUpdate schemas */
export const CAMERA_FOLDER_PATH_CONSTRAINTS = {
  minLength: 1,
  maxLength: 500,
} as const;

/**
 * Camera status enum values from backend CameraStatus enum.
 * See: backend/models/enums.py
 */
export const CAMERA_STATUS_VALUES = ['online', 'offline', 'error', 'unknown'] as const;

/** Type derived from camera status values */
export type CameraStatusValue = (typeof CAMERA_STATUS_VALUES)[number];

// =============================================================================
// Custom Validators (aligned with backend _validate_folder_path)
// =============================================================================

/**
 * Regex for forbidden printable path characters.
 * Aligned with backend: _FORBIDDEN_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
 * Note: Control characters (0x00-0x1f) are checked separately to avoid ESLint warnings.
 */
const FORBIDDEN_PRINTABLE_CHARS = /[<>:"|?*]/;

/**
 * Checks if a path contains control characters (0x00-0x1f).
 */
function containsControlChars(path: string): boolean {
  for (let i = 0; i < path.length; i++) {
    const charCode = path.charCodeAt(i);
    if (charCode >= 0x00 && charCode <= 0x1f) {
      return true;
    }
  }
  return false;
}

/**
 * Validates folder path for security issues.
 * Matches backend _validate_folder_path() in camera.py
 */
function validateFolderPath(path: string): string | true {
  // Check for path traversal attempts
  if (path.includes('..')) {
    return 'Path traversal (..) is not allowed in folder path';
  }

  // Check for forbidden printable characters
  if (FORBIDDEN_PRINTABLE_CHARS.test(path)) {
    return 'Folder path contains forbidden characters (< > : " | ? * or control characters)';
  }

  // Check for control characters
  if (containsControlChars(path)) {
    return 'Folder path contains forbidden characters (< > : " | ? * or control characters)';
  }

  return true;
}

// =============================================================================
// Zod Schemas
// =============================================================================

/**
 * Camera status schema - matches backend CameraStatus enum.
 */
export const cameraStatusSchema = z.enum(CAMERA_STATUS_VALUES, {
  error: 'Invalid camera status. Must be: online, offline, error, or unknown',
});

/**
 * Camera name schema - matches backend CameraCreate.name field.
 * Backend constraint: min_length=1, max_length=255
 */
export const cameraNameSchema = z
  .string()
  .min(CAMERA_NAME_CONSTRAINTS.minLength, { message: 'Name is required' })
  .max(CAMERA_NAME_CONSTRAINTS.maxLength, {
    message: `Name must be at most ${CAMERA_NAME_CONSTRAINTS.maxLength} characters`,
  })
  .transform((val) => val.trim());

/**
 * Camera folder path schema - matches backend CameraCreate.folder_path field.
 * Backend constraints:
 * - min_length=1, max_length=500
 * - No path traversal (..)
 * - No forbidden characters (< > : " | ? * or control characters)
 */
export const cameraFolderPathSchema = z
  .string()
  .min(CAMERA_FOLDER_PATH_CONSTRAINTS.minLength, { message: 'Folder path is required' })
  .max(CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength, {
    message: `Folder path must be at most ${CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength} characters`,
  })
  .superRefine((val, ctx) => {
    const result = validateFolderPath(val);
    if (result !== true) {
      ctx.addIssue({
        code: 'custom',
        message: result,
      });
    }
  })
  .transform((val) => val.trim());

/**
 * Schema for creating a new camera.
 * Matches backend CameraCreate Pydantic model.
 * NEM-3597: Added property_id for multi-property organization.
 */
export const cameraCreateSchema = z.object({
  name: cameraNameSchema,
  folder_path: cameraFolderPathSchema,
  status: cameraStatusSchema.default('online'),
  property_id: z.number().int().positive().nullish(),
});

/**
 * Schema for updating an existing camera.
 * Matches backend CameraUpdate Pydantic model.
 * All fields are optional for partial updates.
 * NEM-3597: Added property_id for multi-property organization.
 */
export const cameraUpdateSchema = z.object({
  name: cameraNameSchema.optional(),
  folder_path: cameraFolderPathSchema.optional(),
  status: cameraStatusSchema.optional(),
  property_id: z.number().int().positive().nullish(),
});

/**
 * Schema for the camera form (used in CamerasSettings.tsx).
 * All fields are required for form display but status has a default.
 * NEM-3597: Added property_id for multi-property organization.
 */
export const cameraFormSchema = z.object({
  name: cameraNameSchema,
  folder_path: cameraFolderPathSchema,
  status: cameraStatusSchema,
  property_id: z.number().int().positive().nullish(),
});

/**
 * Schema for area summary in camera context (minimal area info).
 * NEM-3597: Provides minimal area information for camera responses.
 */
export const cameraAreaSummarySchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
  color: z.string(),
});

/**
 * Schema for camera response from API.
 * Matches backend CameraResponse Pydantic model.
 * NEM-3597: Added property_id and areas for camera organization.
 */
export const cameraResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  folder_path: z.string(),
  status: cameraStatusSchema,
  created_at: z.string().datetime(),
  last_seen_at: z.string().datetime().nullish(),
  property_id: z.number().int().positive().nullish(),
  areas: z.array(cameraAreaSummarySchema).default([]),
});

// =============================================================================
// Type Exports
// =============================================================================

/** Type for CameraCreate payload */
export type CameraCreateInput = z.input<typeof cameraCreateSchema>;
export type CameraCreateOutput = z.output<typeof cameraCreateSchema>;

/** Type for CameraUpdate payload */
export type CameraUpdateInput = z.input<typeof cameraUpdateSchema>;
export type CameraUpdateOutput = z.output<typeof cameraUpdateSchema>;

/** Type for camera form data */
export type CameraFormInput = z.input<typeof cameraFormSchema>;
export type CameraFormOutput = z.output<typeof cameraFormSchema>;

/** Type for area summary in camera context (NEM-3597) */
export type CameraAreaSummary = z.infer<typeof cameraAreaSummarySchema>;

/** Type for camera response from API (NEM-3597) */
export type CameraResponse = z.infer<typeof cameraResponseSchema>;
