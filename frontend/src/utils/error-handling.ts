/**
 * Error Code to UI Mapping Utilities
 *
 * This module provides utilities for handling RFC 7807 structured errors
 * from the backend, mapping error codes to user-friendly messages and
 * appropriate UI treatments (toast variants, retry eligibility, etc.).
 *
 * The backend returns errors in this format:
 * {
 *   "type": "about:blank",
 *   "title": "Not Found",
 *   "status": 404,
 *   "detail": "Camera 'front_door' not found",
 *   "error_code": "CAMERA_NOT_FOUND"
 * }
 *
 * @example
 * ```typescript
 * import { handleApiError, shouldRetry } from './error-handling';
 *
 * try {
 *   await api.getCamera(id);
 * } catch (error) {
 *   const config = handleApiError(error);
 *   if (config.retryable) {
 *     // Schedule retry
 *   }
 * }
 * ```
 */

import { toast } from 'sonner';

import { ApiError, isTimeoutError } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Toast notification variants matching sonner/useToast API
 */
export type ToastVariant = 'error' | 'warning' | 'info';

/**
 * Configuration for how an error should be displayed in the UI
 */
export interface ErrorConfig {
  /** User-friendly error message */
  message: string;
  /** Toast notification variant */
  variant: ToastVariant;
  /** Whether the error is eligible for automatic retry */
  retryable: boolean;
  /** Optional: seconds until retry is appropriate (from rate limiting) */
  retryAfter?: number;
}

// ============================================================================
// Error Codes - Mirroring backend/api/schemas/errors.py
// ============================================================================

/**
 * Machine-readable error codes matching the backend ErrorCode class.
 *
 * These codes are returned in the `error_code` field of RFC 7807 Problem Details
 * responses from the backend API.
 */
export const ErrorCode = {
  // Resource not found errors (404)
  CAMERA_NOT_FOUND: 'CAMERA_NOT_FOUND',
  EVENT_NOT_FOUND: 'EVENT_NOT_FOUND',
  DETECTION_NOT_FOUND: 'DETECTION_NOT_FOUND',
  ZONE_NOT_FOUND: 'ZONE_NOT_FOUND',
  ALERT_NOT_FOUND: 'ALERT_NOT_FOUND',
  ALERT_RULE_NOT_FOUND: 'ALERT_RULE_NOT_FOUND',
  SCENE_CHANGE_NOT_FOUND: 'SCENE_CHANGE_NOT_FOUND',
  LOG_NOT_FOUND: 'LOG_NOT_FOUND',
  AUDIT_LOG_NOT_FOUND: 'AUDIT_LOG_NOT_FOUND',
  ENTITY_NOT_FOUND: 'ENTITY_NOT_FOUND',
  CLIP_NOT_FOUND: 'CLIP_NOT_FOUND',
  PROMPT_NOT_FOUND: 'PROMPT_NOT_FOUND',
  RESOURCE_NOT_FOUND: 'RESOURCE_NOT_FOUND',

  // Validation errors (400, 422)
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  INVALID_DATE_RANGE: 'INVALID_DATE_RANGE',
  INVALID_PAGINATION: 'INVALID_PAGINATION',
  INVALID_FILTER: 'INVALID_FILTER',
  INVALID_REQUEST_BODY: 'INVALID_REQUEST_BODY',
  INVALID_QUERY_PARAMETER: 'INVALID_QUERY_PARAMETER',
  INVALID_PATH_PARAMETER: 'INVALID_PATH_PARAMETER',
  INVALID_CAMERA_ID: 'INVALID_CAMERA_ID',
  INVALID_COORDINATES: 'INVALID_COORDINATES',
  INVALID_CONFIDENCE_THRESHOLD: 'INVALID_CONFIDENCE_THRESHOLD',

  // Conflict errors (409)
  RESOURCE_ALREADY_EXISTS: 'RESOURCE_ALREADY_EXISTS',
  CAMERA_ALREADY_EXISTS: 'CAMERA_ALREADY_EXISTS',
  ZONE_ALREADY_EXISTS: 'ZONE_ALREADY_EXISTS',
  ALERT_RULE_ALREADY_EXISTS: 'ALERT_RULE_ALREADY_EXISTS',
  DUPLICATE_ENTRY: 'DUPLICATE_ENTRY',

  // Authentication/Authorization errors (401, 403)
  AUTHENTICATION_REQUIRED: 'AUTHENTICATION_REQUIRED',
  INVALID_API_KEY: 'INVALID_API_KEY', // pragma: allowlist secret
  EXPIRED_TOKEN: 'EXPIRED_TOKEN',
  ACCESS_DENIED: 'ACCESS_DENIED',
  INSUFFICIENT_PERMISSIONS: 'INSUFFICIENT_PERMISSIONS',

  // Rate limiting errors (429)
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  QUOTA_EXCEEDED: 'QUOTA_EXCEEDED',

  // Transient/Infrastructure errors (500, 502, 503)
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  TIMEOUT: 'TIMEOUT',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  DATABASE_ERROR: 'DATABASE_ERROR',
  CACHE_ERROR: 'CACHE_ERROR',
  QUEUE_ERROR: 'QUEUE_ERROR',

  // AI/ML Service errors (502, 503)
  DETECTOR_UNAVAILABLE: 'DETECTOR_UNAVAILABLE',
  RTDETR_UNAVAILABLE: 'RTDETR_UNAVAILABLE',
  NEMOTRON_UNAVAILABLE: 'NEMOTRON_UNAVAILABLE',
  FLORENCE_UNAVAILABLE: 'FLORENCE_UNAVAILABLE',
  ENRICHMENT_SERVICE_UNAVAILABLE: 'ENRICHMENT_SERVICE_UNAVAILABLE',
  AI_SERVICE_TIMEOUT: 'AI_SERVICE_TIMEOUT',
  MODEL_LOAD_FAILED: 'MODEL_LOAD_FAILED',
  INFERENCE_FAILED: 'INFERENCE_FAILED',

  // File/Media errors
  FILE_NOT_FOUND: 'FILE_NOT_FOUND',
  FILE_ACCESS_DENIED: 'FILE_ACCESS_DENIED',
  INVALID_FILE_TYPE: 'INVALID_FILE_TYPE',
  FILE_TOO_LARGE: 'FILE_TOO_LARGE',
  MEDIA_PROCESSING_FAILED: 'MEDIA_PROCESSING_FAILED',
  THUMBNAIL_GENERATION_FAILED: 'THUMBNAIL_GENERATION_FAILED',
  CLIP_GENERATION_FAILED: 'CLIP_GENERATION_FAILED',

  // WebSocket errors
  WEBSOCKET_CONNECTION_FAILED: 'WEBSOCKET_CONNECTION_FAILED',
  INVALID_WEBSOCKET_MESSAGE: 'INVALID_WEBSOCKET_MESSAGE',
  SUBSCRIPTION_FAILED: 'SUBSCRIPTION_FAILED',

  // Configuration errors
  INVALID_CONFIGURATION: 'INVALID_CONFIGURATION',
  CONFIGURATION_UPDATE_FAILED: 'CONFIGURATION_UPDATE_FAILED',

  // Operation errors
  OPERATION_FAILED: 'OPERATION_FAILED',
  OPERATION_TIMEOUT: 'OPERATION_TIMEOUT',
  OPERATION_CANCELLED: 'OPERATION_CANCELLED',

  // Unknown/fallback
  UNKNOWN: 'UNKNOWN',
} as const;

export type ErrorCodeType = (typeof ErrorCode)[keyof typeof ErrorCode];

// ============================================================================
// Error Code to Config Mapping
// ============================================================================

/**
 * Map of error codes to their UI configuration.
 *
 * This mapping determines:
 * - The user-friendly message to display
 * - The toast variant (error, warning, info)
 * - Whether the error is eligible for automatic retry
 */
const ERROR_CONFIG_MAP: Record<string, ErrorConfig> = {
  // Resource not found errors - Non-retryable, error variant
  [ErrorCode.CAMERA_NOT_FOUND]: {
    message: 'Camera not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.EVENT_NOT_FOUND]: {
    message: 'Event not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.DETECTION_NOT_FOUND]: {
    message: 'Detection not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.ZONE_NOT_FOUND]: {
    message: 'Zone not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.ALERT_NOT_FOUND]: {
    message: 'Alert not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.ALERT_RULE_NOT_FOUND]: {
    message: 'Alert rule not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.SCENE_CHANGE_NOT_FOUND]: {
    message: 'Scene change not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.LOG_NOT_FOUND]: {
    message: 'Log entry not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.AUDIT_LOG_NOT_FOUND]: {
    message: 'Audit log not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.ENTITY_NOT_FOUND]: {
    message: 'Entity not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.CLIP_NOT_FOUND]: {
    message: 'Video clip not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.PROMPT_NOT_FOUND]: {
    message: 'Prompt not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.RESOURCE_NOT_FOUND]: {
    message: 'Resource not found',
    variant: 'error',
    retryable: false,
  },

  // Validation errors - Non-retryable, warning variant (user can fix)
  [ErrorCode.VALIDATION_ERROR]: {
    message: 'Invalid request data',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_DATE_RANGE]: {
    message: 'Invalid date range',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_PAGINATION]: {
    message: 'Invalid pagination parameters',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_FILTER]: {
    message: 'Invalid filter parameters',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_REQUEST_BODY]: {
    message: 'Invalid request body',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_QUERY_PARAMETER]: {
    message: 'Invalid query parameter',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_PATH_PARAMETER]: {
    message: 'Invalid path parameter',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_CAMERA_ID]: {
    message: 'Invalid camera ID',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_COORDINATES]: {
    message: 'Invalid coordinates',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.INVALID_CONFIDENCE_THRESHOLD]: {
    message: 'Invalid confidence threshold',
    variant: 'warning',
    retryable: false,
  },

  // Conflict errors - Non-retryable, warning variant
  [ErrorCode.RESOURCE_ALREADY_EXISTS]: {
    message: 'Resource already exists',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.CAMERA_ALREADY_EXISTS]: {
    message: 'Camera already exists',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.ZONE_ALREADY_EXISTS]: {
    message: 'Zone already exists',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.ALERT_RULE_ALREADY_EXISTS]: {
    message: 'Alert rule already exists',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.DUPLICATE_ENTRY]: {
    message: 'Duplicate entry',
    variant: 'warning',
    retryable: false,
  },

  // Authentication errors - Non-retryable, error variant
  [ErrorCode.AUTHENTICATION_REQUIRED]: {
    message: 'Authentication required',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.INVALID_API_KEY]: {
    message: 'Invalid API key',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.EXPIRED_TOKEN]: {
    message: 'Session expired. Please log in again.',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.ACCESS_DENIED]: {
    message: 'Access denied',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.INSUFFICIENT_PERMISSIONS]: {
    message: 'Insufficient permissions',
    variant: 'error',
    retryable: false,
  },

  // Rate limiting - Retryable, warning variant
  [ErrorCode.RATE_LIMIT_EXCEEDED]: {
    message: 'Rate limit exceeded. Please try again later.',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.QUOTA_EXCEEDED]: {
    message: 'Quota exceeded',
    variant: 'warning',
    retryable: true,
  },

  // Transient infrastructure errors - Retryable
  [ErrorCode.SERVICE_UNAVAILABLE]: {
    message: 'Service temporarily unavailable',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.TIMEOUT]: {
    message: 'Request timed out',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.DATABASE_ERROR]: {
    message: 'Database error occurred',
    variant: 'error',
    retryable: true,
  },
  [ErrorCode.CACHE_ERROR]: {
    message: 'Cache error occurred',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.QUEUE_ERROR]: {
    message: 'Queue error occurred',
    variant: 'warning',
    retryable: true,
  },

  // Internal error - Non-retryable (likely a bug)
  [ErrorCode.INTERNAL_ERROR]: {
    message: 'An unexpected error occurred',
    variant: 'error',
    retryable: false,
  },

  // AI/ML Service errors - Retryable (services may recover)
  [ErrorCode.DETECTOR_UNAVAILABLE]: {
    message: 'Object detection service unavailable',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.RTDETR_UNAVAILABLE]: {
    message: 'RT-DETR detection service unavailable',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.NEMOTRON_UNAVAILABLE]: {
    message: 'Nemotron analysis service unavailable',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.FLORENCE_UNAVAILABLE]: {
    message: 'Florence service unavailable',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.ENRICHMENT_SERVICE_UNAVAILABLE]: {
    message: 'Enrichment service unavailable',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.AI_SERVICE_TIMEOUT]: {
    message: 'AI service request timed out',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.MODEL_LOAD_FAILED]: {
    message: 'Failed to load AI model',
    variant: 'error',
    retryable: true,
  },
  [ErrorCode.INFERENCE_FAILED]: {
    message: 'AI inference failed',
    variant: 'error',
    retryable: true,
  },

  // File/Media errors - Mixed retryability
  [ErrorCode.FILE_NOT_FOUND]: {
    message: 'File not found',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.FILE_ACCESS_DENIED]: {
    message: 'File access denied',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.INVALID_FILE_TYPE]: {
    message: 'Invalid file type',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.FILE_TOO_LARGE]: {
    message: 'File size exceeds limit',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.MEDIA_PROCESSING_FAILED]: {
    message: 'Media processing failed',
    variant: 'error',
    retryable: true,
  },
  [ErrorCode.THUMBNAIL_GENERATION_FAILED]: {
    message: 'Thumbnail generation failed',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.CLIP_GENERATION_FAILED]: {
    message: 'Video clip generation failed',
    variant: 'error',
    retryable: true,
  },

  // WebSocket errors - Mixed retryability
  [ErrorCode.WEBSOCKET_CONNECTION_FAILED]: {
    message: 'WebSocket connection failed',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.INVALID_WEBSOCKET_MESSAGE]: {
    message: 'Invalid WebSocket message',
    variant: 'warning',
    retryable: false,
  },
  [ErrorCode.SUBSCRIPTION_FAILED]: {
    message: 'Subscription failed',
    variant: 'warning',
    retryable: true,
  },

  // Configuration errors - Non-retryable
  [ErrorCode.INVALID_CONFIGURATION]: {
    message: 'Invalid configuration',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.CONFIGURATION_UPDATE_FAILED]: {
    message: 'Configuration update failed',
    variant: 'error',
    retryable: false,
  },

  // Operation errors - Mixed retryability
  [ErrorCode.OPERATION_FAILED]: {
    message: 'Operation failed',
    variant: 'error',
    retryable: false,
  },
  [ErrorCode.OPERATION_TIMEOUT]: {
    message: 'Operation timed out',
    variant: 'warning',
    retryable: true,
  },
  [ErrorCode.OPERATION_CANCELLED]: {
    message: 'Operation was cancelled',
    variant: 'info',
    retryable: false,
  },

  // Unknown/fallback
  [ErrorCode.UNKNOWN]: {
    message: 'An unexpected error occurred',
    variant: 'error',
    retryable: false,
  },
};

/**
 * Default error configuration for unknown error codes.
 */
const DEFAULT_ERROR_CONFIG: ErrorConfig = {
  message: 'An unexpected error occurred',
  variant: 'error',
  retryable: false,
};

// ============================================================================
// Retryable Error Codes Set
// ============================================================================

/**
 * Set of error codes that are eligible for automatic retry.
 *
 * These are typically transient errors that may succeed on retry:
 * - Service availability issues (503, 502)
 * - Rate limiting (429)
 * - Timeouts
 * - AI service errors
 */
const RETRYABLE_ERROR_CODES = new Set<string>([
  // Transient infrastructure
  ErrorCode.SERVICE_UNAVAILABLE,
  ErrorCode.TIMEOUT,
  ErrorCode.DATABASE_ERROR,
  ErrorCode.CACHE_ERROR,
  ErrorCode.QUEUE_ERROR,

  // Rate limiting
  ErrorCode.RATE_LIMIT_EXCEEDED,
  ErrorCode.QUOTA_EXCEEDED,

  // AI/ML services
  ErrorCode.DETECTOR_UNAVAILABLE,
  ErrorCode.RTDETR_UNAVAILABLE,
  ErrorCode.NEMOTRON_UNAVAILABLE,
  ErrorCode.FLORENCE_UNAVAILABLE,
  ErrorCode.ENRICHMENT_SERVICE_UNAVAILABLE,
  ErrorCode.AI_SERVICE_TIMEOUT,
  ErrorCode.MODEL_LOAD_FAILED,
  ErrorCode.INFERENCE_FAILED,

  // Media processing
  ErrorCode.MEDIA_PROCESSING_FAILED,
  ErrorCode.THUMBNAIL_GENERATION_FAILED,
  ErrorCode.CLIP_GENERATION_FAILED,

  // WebSocket
  ErrorCode.WEBSOCKET_CONNECTION_FAILED,
  ErrorCode.SUBSCRIPTION_FAILED,

  // Operations
  ErrorCode.OPERATION_TIMEOUT,
]);

/**
 * HTTP status codes that are generally retryable regardless of error_code.
 */
const RETRYABLE_HTTP_STATUS_CODES = new Set([
  429, // Too Many Requests (rate limited)
  502, // Bad Gateway
  503, // Service Unavailable
  504, // Gateway Timeout
]);

// ============================================================================
// Public Functions
// ============================================================================

/**
 * Get the error configuration for a given error code.
 *
 * @param errorCode - The machine-readable error code from the backend
 * @returns ErrorConfig with message, variant, and retryable flag
 *
 * @example
 * ```typescript
 * const config = getErrorConfig('CAMERA_NOT_FOUND');
 * console.log(config.message); // 'Camera not found'
 * console.log(config.variant); // 'error'
 * console.log(config.retryable); // false
 * ```
 */
export function getErrorConfig(errorCode: string): ErrorConfig {
  return ERROR_CONFIG_MAP[errorCode] ?? DEFAULT_ERROR_CONFIG;
}

/**
 * Check if an error code is eligible for automatic retry.
 *
 * @param errorCode - The machine-readable error code from the backend
 * @returns true if the error is transient and may succeed on retry
 *
 * @example
 * ```typescript
 * if (isRetryableErrorCode('SERVICE_UNAVAILABLE')) {
 *   // Schedule retry with exponential backoff
 * }
 * ```
 */
export function isRetryableErrorCode(errorCode: string): boolean {
  return RETRYABLE_ERROR_CODES.has(errorCode);
}

/**
 * Determine if an error should be retried.
 *
 * Checks multiple signals to determine retry eligibility:
 * 1. If error is a TimeoutError, always retryable
 * 2. If error is an ApiError with a retryable error_code
 * 3. If error is an ApiError with a retryable HTTP status code
 *
 * @param error - The error to check (ApiError, TimeoutError, or unknown)
 * @returns true if the error is eligible for automatic retry
 *
 * @example
 * ```typescript
 * try {
 *   await api.getEvents();
 * } catch (error) {
 *   if (shouldRetry(error)) {
 *     // Implement retry logic with exponential backoff
 *   }
 * }
 * ```
 */
export function shouldRetry(error: unknown): boolean {
  // Handle null/undefined
  if (error === null || error === undefined) {
    return false;
  }

  // TimeoutError is always retryable
  if (isTimeoutError(error)) {
    return true;
  }

  // Check ApiError
  if (error instanceof ApiError) {
    // Check for error_code in problemDetails
    const errorCode = error.problemDetails?.error_code as string | undefined;
    if (errorCode && isRetryableErrorCode(errorCode)) {
      return true;
    }

    // Check HTTP status code
    if (RETRYABLE_HTTP_STATUS_CODES.has(error.status)) {
      return true;
    }

    return false;
  }

  // Generic errors are not retryable
  return false;
}

/**
 * Extract error code from an error object.
 *
 * @param error - The error to extract code from
 * @returns The error code string, or 'UNKNOWN' if not found
 */
function extractErrorCode(error: unknown): string {
  if (error instanceof ApiError) {
    // Check for error_code in problemDetails
    const errorCode = error.problemDetails?.error_code as string | undefined;
    if (errorCode) {
      return errorCode;
    }

    // Fall back to HTTP status-based mapping
    switch (error.status) {
      case 429:
        return ErrorCode.RATE_LIMIT_EXCEEDED;
      case 503:
        return ErrorCode.SERVICE_UNAVAILABLE;
      case 504:
        return ErrorCode.TIMEOUT;
      default:
        return ErrorCode.UNKNOWN;
    }
  }

  if (isTimeoutError(error)) {
    return ErrorCode.TIMEOUT;
  }

  return ErrorCode.UNKNOWN;
}

/**
 * Handle an API error by showing an appropriate toast notification
 * and returning the error configuration.
 *
 * This is the main entry point for error handling in the UI. It:
 * 1. Extracts the error code from the error
 * 2. Looks up the appropriate user-friendly message
 * 3. Shows a toast notification with the correct variant
 * 4. Returns the error configuration for further handling
 *
 * @param error - The error to handle (ApiError, TimeoutError, or unknown)
 * @returns ErrorConfig with message, variant, retryable flag, and optional retryAfter
 *
 * @example
 * ```typescript
 * import { handleApiError } from './error-handling';
 *
 * try {
 *   await api.deleteCamera(id);
 * } catch (error) {
 *   const config = handleApiError(error);
 *
 *   if (config.retryable && config.retryAfter) {
 *     // Wait retryAfter seconds before retrying
 *     setTimeout(() => retry(), config.retryAfter * 1000);
 *   }
 * }
 * ```
 */
export function handleApiError(error: unknown): ErrorConfig {
  const errorCode = extractErrorCode(error);
  const config = getErrorConfig(errorCode);

  // Extract additional details for the toast
  let description: string | undefined;
  let retryAfter: number | undefined;

  if (error instanceof ApiError && error.problemDetails) {
    // Use the detail field from RFC 7807 as the description
    if (error.problemDetails.detail && error.problemDetails.detail !== config.message) {
      description = error.problemDetails.detail;
    }

    // Extract retry_after for rate limiting
    retryAfter = error.problemDetails.retry_after as number | undefined;
  }

  // Show the appropriate toast
  const toastOptions: { description?: string } = {};
  if (description) {
    toastOptions.description = description;
  }

  switch (config.variant) {
    case 'error':
      toast.error(config.message, toastOptions);
      break;
    case 'warning':
      toast.warning(config.message, toastOptions);
      break;
    case 'info':
      toast.info(config.message, toastOptions);
      break;
  }

  // Return config with optional retryAfter
  return {
    ...config,
    ...(retryAfter !== undefined && { retryAfter }),
  };
}
