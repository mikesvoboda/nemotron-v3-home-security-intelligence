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

/**
 * Ingestion mode enum values for camera configuration.
 * Determines how the camera sends images to the system.
 */
export const INGESTION_MODE_VALUES = ['ftp', 'rtsp', 'onvif'] as const;

/** Type derived from ingestion mode values */
export type IngestionModeValue = (typeof INGESTION_MODE_VALUES)[number];

/**
 * Stream profile enum values for RTSP cameras.
 * Determines which stream to use from multi-stream cameras.
 */
export const STREAM_PROFILE_VALUES = ['main', 'sub', 'both'] as const;

/** Type derived from stream profile values */
export type StreamProfileValue = (typeof STREAM_PROFILE_VALUES)[number];

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
 * Checks if a path is a URL (RTSP, HTTP, HTTPS).
 * URLs are allowed to contain colons for the protocol separator.
 */
function isUrl(path: string): boolean {
  const lowerPath = path.toLowerCase();
  return lowerPath.startsWith('rtsp://') ||
         lowerPath.startsWith('http://') ||
         lowerPath.startsWith('https://');
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

  // Skip forbidden character check for URLs (RTSP/HTTP/HTTPS)
  // URLs legitimately contain colons for the protocol separator
  if (!isUrl(path)) {
    // Check for forbidden printable characters
    if (FORBIDDEN_PRINTABLE_CHARS.test(path)) {
      return 'Folder path contains forbidden characters (< > : " | ? * or control characters)';
    }
  }

  // Check for control characters (always forbidden, even in URLs)
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
  .min(CAMERA_NAME_CONSTRAINTS.minLength, { error: 'Name is required' })
  .max(CAMERA_NAME_CONSTRAINTS.maxLength, {
    error: `Name must be at most ${CAMERA_NAME_CONSTRAINTS.maxLength} characters`,
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
  .min(CAMERA_FOLDER_PATH_CONSTRAINTS.minLength, { error: 'Folder path is required' })
  .max(CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength, {
    error: `Folder path must be at most ${CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength} characters`,
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
 * Motion sensitivity schema - validates range 0.0-1.0.
 * Only applicable to RTSP cameras; optional for all cameras.
 */
export const cameraMotionSensitivitySchema = z
  .number()
  .min(0, { message: 'Motion sensitivity must be at least 0' })
  .max(1, { message: 'Motion sensitivity must be at most 1' })
  .optional();

/**
 * Ingestion mode schema - determines how camera sends images.
 * - ftp: Camera uploads images via FTP to a folder
 * - rtsp: System pulls video stream from camera via RTSP
 * - onvif: System uses ONVIF protocol for camera control
 */
export const ingestionModeSchema = z.enum(INGESTION_MODE_VALUES, {
  error: 'Invalid ingestion mode. Must be: ftp, rtsp, or onvif',
});

/**
 * Stream profile schema - which stream to use from RTSP cameras.
 * - main: High quality main stream
 * - sub: Lower quality sub-stream (for bandwidth savings)
 * - both: Process both streams
 */
export const streamProfileSchema = z.enum(STREAM_PROFILE_VALUES, {
  error: 'Invalid stream profile. Must be: main, sub, or both',
}).nullable().optional();

/**
 * Checks if an RTSP URL has a valid format with a host.
 *
 * Valid formats:
 * - rtsp://hostname
 * - rtsp://hostname:port
 * - rtsp://hostname/path
 * - rtsp://user:****@hostname:port/path (with credentials)
 * Invalid: rtsp:///path (missing host)
 */
function isValidRtspUrl(url: string): { valid: boolean; message?: string } {
  if (!url) return { valid: true }; // Empty is handled by refinement

  // Check protocol
  const lowerUrl = url.toLowerCase();
  if (!lowerUrl.startsWith('rtsp://') && !lowerUrl.startsWith('rtsps://')) {
    return { valid: false, message: 'RTSP URL must use rtsp:// or rtsps:// protocol' };
  }

  // Extract the part after the protocol
  const protocolEnd = url.indexOf('://') + 3;
  const afterProtocol = url.slice(protocolEnd);

  // Find where the host ends (at / or end of string)
  const pathStart = afterProtocol.indexOf('/');
  const hostPart = pathStart === -1 ? afterProtocol : afterProtocol.slice(0, pathStart);

  // If there's an @ for auth, get the part after it
  const atIndex = hostPart.lastIndexOf('@');
  const hostAndPort = atIndex === -1 ? hostPart : hostPart.slice(atIndex + 1);

  // Remove port if present
  const colonIndex = hostAndPort.lastIndexOf(':');
  const host = colonIndex === -1 ? hostAndPort : hostAndPort.slice(0, colonIndex);

  // Host must have at least one character
  if (host.length === 0) {
    return { valid: false, message: 'RTSP URL must have a valid host' };
  }

  return { valid: true };
}

/**
 * RTSP URL schema - validates RTSP stream URLs.
 * Requires rtsp:// or rtsps:// protocol with a valid host.
 * Nullable and optional - validation for RTSP/ONVIF mode is handled by refinement.
 */
export const rtspUrlSchema = z
  .string()
  .superRefine((val, ctx) => {
    if (!val) return; // Empty string or null handled elsewhere
    const result = isValidRtspUrl(val);
    if (!result.valid && result.message) {
      ctx.addIssue({
        code: 'custom',
        message: result.message,
      });
    }
  })
  .nullable()
  .optional();

/**
 * RTSP username schema - optional authentication username.
 */
export const rtspUsernameSchema = z.string().nullable().optional();

/**
 * RTSP password schema - optional authentication password.
 */
export const rtspPasswordSchema = z.string().nullable().optional();

/**
 * Base schema for creating a new camera (without refinement).
 * Matches backend CameraCreate Pydantic model.
 */
const cameraCreateBaseSchema = z.object({
  name: cameraNameSchema,
  folder_path: cameraFolderPathSchema,
  status: cameraStatusSchema.default('online'),
  motion_sensitivity: cameraMotionSensitivitySchema,
  ingestion_mode: ingestionModeSchema.optional(),
  rtsp_url: rtspUrlSchema,
  rtsp_username: rtspUsernameSchema,
  rtsp_password: rtspPasswordSchema,
  stream_profile: streamProfileSchema,
});

/**
 * Schema for creating a new camera with cross-field validation.
 * Matches backend CameraCreate Pydantic model.
 *
 * Refinement: rtsp_url is required when ingestion_mode is 'rtsp' or 'onvif'
 */
export const cameraCreateSchema = cameraCreateBaseSchema.refine(
  (data) => {
    if (data.ingestion_mode === 'rtsp' || data.ingestion_mode === 'onvif') {
      return data.rtsp_url && data.rtsp_url.length > 0;
    }
    return true;
  },
  {
    message: 'RTSP URL is required when ingestion mode is RTSP or ONVIF',
    path: ['rtsp_url'],
  }
);

/**
 * Schema for updating an existing camera.
 * Matches backend CameraUpdate Pydantic model.
 * All fields are optional for partial updates.
 */
export const cameraUpdateSchema = z.object({
  name: cameraNameSchema.optional(),
  folder_path: cameraFolderPathSchema.optional(),
  status: cameraStatusSchema.optional(),
  motion_sensitivity: cameraMotionSensitivitySchema,
});

/**
 * Base schema for the camera form (used in CamerasSettings.tsx).
 * All fields are required for form display but status has a default.
 */
const cameraFormBaseSchema = z.object({
  name: cameraNameSchema,
  folder_path: cameraFolderPathSchema,
  status: cameraStatusSchema,
  motion_sensitivity: cameraMotionSensitivitySchema,
  ingestion_mode: ingestionModeSchema.default('ftp'),
  rtsp_url: rtspUrlSchema,
  rtsp_username: rtspUsernameSchema,
  rtsp_password: rtspPasswordSchema,
  stream_profile: streamProfileSchema,
});

/**
 * Schema for the camera form with cross-field validation.
 * Used in CamerasSettings.tsx for form validation.
 *
 * Refinement: rtsp_url is required when ingestion_mode is 'rtsp' or 'onvif'
 */
export const cameraFormSchema = cameraFormBaseSchema.refine(
  (data) => {
    if (data.ingestion_mode === 'rtsp' || data.ingestion_mode === 'onvif') {
      return data.rtsp_url && data.rtsp_url.length > 0;
    }
    return true;
  },
  {
    message: 'RTSP URL is required when ingestion mode is RTSP or ONVIF',
    path: ['rtsp_url'],
  }
);

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
