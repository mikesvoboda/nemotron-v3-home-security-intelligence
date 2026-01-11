/**
 * Tests for error-handling utilities
 *
 * Tests the error code to UI mapping functionality that handles
 * RFC 7807 structured errors from the backend.
 */

import { toast } from 'sonner';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import {
  ErrorCode,
  type ErrorConfig,
  getErrorConfig,
  handleApiError,
  shouldRetry,
  isRetryableErrorCode,
} from './error-handling';
import { ApiError, type ProblemDetails, TimeoutError } from '../services/api';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(() => 'toast-id'),
    warning: vi.fn(() => 'toast-id'),
    info: vi.fn(() => 'toast-id'),
  },
}));

describe('error-handling utilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('ErrorCode', () => {
    it('exports all expected error code constants', () => {
      // Resource not found errors
      expect(ErrorCode.CAMERA_NOT_FOUND).toBe('CAMERA_NOT_FOUND');
      expect(ErrorCode.EVENT_NOT_FOUND).toBe('EVENT_NOT_FOUND');
      expect(ErrorCode.DETECTION_NOT_FOUND).toBe('DETECTION_NOT_FOUND');
      expect(ErrorCode.ZONE_NOT_FOUND).toBe('ZONE_NOT_FOUND');
      expect(ErrorCode.RESOURCE_NOT_FOUND).toBe('RESOURCE_NOT_FOUND');

      // Validation errors
      expect(ErrorCode.VALIDATION_ERROR).toBe('VALIDATION_ERROR');
      expect(ErrorCode.INVALID_DATE_RANGE).toBe('INVALID_DATE_RANGE');
      expect(ErrorCode.INVALID_PAGINATION).toBe('INVALID_PAGINATION');

      // Transient errors
      expect(ErrorCode.SERVICE_UNAVAILABLE).toBe('SERVICE_UNAVAILABLE');
      expect(ErrorCode.RATE_LIMIT_EXCEEDED).toBe('RATE_LIMIT_EXCEEDED');
      expect(ErrorCode.TIMEOUT).toBe('TIMEOUT');

      // AI pipeline errors
      expect(ErrorCode.DETECTOR_UNAVAILABLE).toBe('DETECTOR_UNAVAILABLE');
      expect(ErrorCode.INFERENCE_FAILED).toBe('INFERENCE_FAILED');
      expect(ErrorCode.MODEL_LOAD_FAILED).toBe('MODEL_LOAD_FAILED');

      // Auth errors
      expect(ErrorCode.AUTHENTICATION_REQUIRED).toBe('AUTHENTICATION_REQUIRED');
      expect(ErrorCode.EXPIRED_TOKEN).toBe('EXPIRED_TOKEN');
      expect(ErrorCode.ACCESS_DENIED).toBe('ACCESS_DENIED');

      // Unknown error fallback
      expect(ErrorCode.UNKNOWN).toBe('UNKNOWN');
    });
  });

  describe('getErrorConfig', () => {
    describe('resource not found errors (404)', () => {
      it('returns config for CAMERA_NOT_FOUND', () => {
        const config = getErrorConfig(ErrorCode.CAMERA_NOT_FOUND);
        expect(config.message).toBe('Camera not found');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for EVENT_NOT_FOUND', () => {
        const config = getErrorConfig(ErrorCode.EVENT_NOT_FOUND);
        expect(config.message).toBe('Event not found');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for DETECTION_NOT_FOUND', () => {
        const config = getErrorConfig(ErrorCode.DETECTION_NOT_FOUND);
        expect(config.message).toBe('Detection not found');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for ZONE_NOT_FOUND', () => {
        const config = getErrorConfig(ErrorCode.ZONE_NOT_FOUND);
        expect(config.message).toBe('Zone not found');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for ALERT_NOT_FOUND', () => {
        const config = getErrorConfig(ErrorCode.ALERT_NOT_FOUND);
        expect(config.message).toBe('Alert not found');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for RESOURCE_NOT_FOUND', () => {
        const config = getErrorConfig(ErrorCode.RESOURCE_NOT_FOUND);
        expect(config.message).toBe('Resource not found');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });
    });

    describe('validation errors (400, 422)', () => {
      it('returns config for VALIDATION_ERROR', () => {
        const config = getErrorConfig(ErrorCode.VALIDATION_ERROR);
        expect(config.message).toBe('Invalid request data');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });

      it('returns config for INVALID_DATE_RANGE', () => {
        const config = getErrorConfig(ErrorCode.INVALID_DATE_RANGE);
        expect(config.message).toBe('Invalid date range');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });

      it('returns config for INVALID_PAGINATION', () => {
        const config = getErrorConfig(ErrorCode.INVALID_PAGINATION);
        expect(config.message).toBe('Invalid pagination parameters');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });

      it('returns config for INVALID_REQUEST_BODY', () => {
        const config = getErrorConfig(ErrorCode.INVALID_REQUEST_BODY);
        expect(config.message).toBe('Invalid request body');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });
    });

    describe('transient errors (retryable)', () => {
      it('returns config for SERVICE_UNAVAILABLE', () => {
        const config = getErrorConfig(ErrorCode.SERVICE_UNAVAILABLE);
        expect(config.message).toBe('Service temporarily unavailable');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });

      it('returns config for RATE_LIMIT_EXCEEDED', () => {
        const config = getErrorConfig(ErrorCode.RATE_LIMIT_EXCEEDED);
        expect(config.message).toBe('Rate limit exceeded. Please try again later.');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });

      it('returns config for TIMEOUT', () => {
        const config = getErrorConfig(ErrorCode.TIMEOUT);
        expect(config.message).toBe('Request timed out');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });

      it('returns config for DATABASE_ERROR', () => {
        const config = getErrorConfig(ErrorCode.DATABASE_ERROR);
        expect(config.message).toBe('Database error occurred');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(true);
      });

      it('returns config for CACHE_ERROR', () => {
        const config = getErrorConfig(ErrorCode.CACHE_ERROR);
        expect(config.message).toBe('Cache error occurred');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });
    });

    describe('AI pipeline errors', () => {
      it('returns config for DETECTOR_UNAVAILABLE', () => {
        const config = getErrorConfig(ErrorCode.DETECTOR_UNAVAILABLE);
        expect(config.message).toBe('Object detection service unavailable');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });

      it('returns config for RTDETR_UNAVAILABLE', () => {
        const config = getErrorConfig(ErrorCode.RTDETR_UNAVAILABLE);
        expect(config.message).toBe('RT-DETR detection service unavailable');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });

      it('returns config for NEMOTRON_UNAVAILABLE', () => {
        const config = getErrorConfig(ErrorCode.NEMOTRON_UNAVAILABLE);
        expect(config.message).toBe('Nemotron analysis service unavailable');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });

      it('returns config for INFERENCE_FAILED', () => {
        const config = getErrorConfig(ErrorCode.INFERENCE_FAILED);
        expect(config.message).toBe('AI inference failed');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(true);
      });

      it('returns config for MODEL_LOAD_FAILED', () => {
        const config = getErrorConfig(ErrorCode.MODEL_LOAD_FAILED);
        expect(config.message).toBe('Failed to load AI model');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(true);
      });

      it('returns config for AI_SERVICE_TIMEOUT', () => {
        const config = getErrorConfig(ErrorCode.AI_SERVICE_TIMEOUT);
        expect(config.message).toBe('AI service request timed out');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(true);
      });
    });

    describe('authentication errors', () => {
      it('returns config for AUTHENTICATION_REQUIRED', () => {
        const config = getErrorConfig(ErrorCode.AUTHENTICATION_REQUIRED);
        expect(config.message).toBe('Authentication required');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for EXPIRED_TOKEN', () => {
        const config = getErrorConfig(ErrorCode.EXPIRED_TOKEN);
        expect(config.message).toBe('Session expired. Please log in again.');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });

      it('returns config for ACCESS_DENIED', () => {
        const config = getErrorConfig(ErrorCode.ACCESS_DENIED);
        expect(config.message).toBe('Access denied');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for INVALID_API_KEY', () => {
        const config = getErrorConfig(ErrorCode.INVALID_API_KEY);
        expect(config.message).toBe('Invalid API key');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });
    });

    describe('conflict errors (409)', () => {
      it('returns config for RESOURCE_ALREADY_EXISTS', () => {
        const config = getErrorConfig(ErrorCode.RESOURCE_ALREADY_EXISTS);
        expect(config.message).toBe('Resource already exists');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });

      it('returns config for CAMERA_ALREADY_EXISTS', () => {
        const config = getErrorConfig(ErrorCode.CAMERA_ALREADY_EXISTS);
        expect(config.message).toBe('Camera already exists');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });

      it('returns config for DUPLICATE_ENTRY', () => {
        const config = getErrorConfig(ErrorCode.DUPLICATE_ENTRY);
        expect(config.message).toBe('Duplicate entry');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });
    });

    describe('file/media errors', () => {
      it('returns config for FILE_NOT_FOUND', () => {
        const config = getErrorConfig(ErrorCode.FILE_NOT_FOUND);
        expect(config.message).toBe('File not found');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns config for FILE_TOO_LARGE', () => {
        const config = getErrorConfig(ErrorCode.FILE_TOO_LARGE);
        expect(config.message).toBe('File size exceeds limit');
        expect(config.variant).toBe('warning');
        expect(config.retryable).toBe(false);
      });

      it('returns config for MEDIA_PROCESSING_FAILED', () => {
        const config = getErrorConfig(ErrorCode.MEDIA_PROCESSING_FAILED);
        expect(config.message).toBe('Media processing failed');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(true);
      });
    });

    describe('internal errors', () => {
      it('returns config for INTERNAL_ERROR', () => {
        const config = getErrorConfig(ErrorCode.INTERNAL_ERROR);
        expect(config.message).toBe('An unexpected error occurred');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });
    });

    describe('unknown error codes', () => {
      it('returns default config for unknown error code', () => {
        const config = getErrorConfig('SOME_UNKNOWN_ERROR');
        expect(config.message).toBe('An unexpected error occurred');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });

      it('returns default config for UNKNOWN error code', () => {
        const config = getErrorConfig(ErrorCode.UNKNOWN);
        expect(config.message).toBe('An unexpected error occurred');
        expect(config.variant).toBe('error');
        expect(config.retryable).toBe(false);
      });
    });
  });

  describe('isRetryableErrorCode', () => {
    it('returns true for transient error codes', () => {
      expect(isRetryableErrorCode(ErrorCode.SERVICE_UNAVAILABLE)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.RATE_LIMIT_EXCEEDED)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.TIMEOUT)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.DATABASE_ERROR)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.CACHE_ERROR)).toBe(true);
    });

    it('returns true for AI service errors', () => {
      expect(isRetryableErrorCode(ErrorCode.DETECTOR_UNAVAILABLE)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.RTDETR_UNAVAILABLE)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.NEMOTRON_UNAVAILABLE)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.INFERENCE_FAILED)).toBe(true);
      expect(isRetryableErrorCode(ErrorCode.AI_SERVICE_TIMEOUT)).toBe(true);
    });

    it('returns false for non-retryable error codes', () => {
      expect(isRetryableErrorCode(ErrorCode.CAMERA_NOT_FOUND)).toBe(false);
      expect(isRetryableErrorCode(ErrorCode.VALIDATION_ERROR)).toBe(false);
      expect(isRetryableErrorCode(ErrorCode.AUTHENTICATION_REQUIRED)).toBe(false);
      expect(isRetryableErrorCode(ErrorCode.ACCESS_DENIED)).toBe(false);
      expect(isRetryableErrorCode(ErrorCode.INTERNAL_ERROR)).toBe(false);
    });

    it('returns false for unknown error codes', () => {
      expect(isRetryableErrorCode('UNKNOWN_ERROR')).toBe(false);
    });
  });

  describe('shouldRetry', () => {
    it('returns true for ApiError with retryable error_code in problemDetails', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Service Unavailable',
        status: 503,
        error_code: ErrorCode.SERVICE_UNAVAILABLE,
      };
      const error = new ApiError(503, 'Service Unavailable', undefined, problemDetails);
      expect(shouldRetry(error)).toBe(true);
    });

    it('returns false for ApiError with non-retryable error_code', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        error_code: ErrorCode.CAMERA_NOT_FOUND,
      };
      const error = new ApiError(404, 'Camera not found', undefined, problemDetails);
      expect(shouldRetry(error)).toBe(false);
    });

    it('returns true for ApiError with status 429 (rate limited)', () => {
      const error = new ApiError(429, 'Rate limited');
      expect(shouldRetry(error)).toBe(true);
    });

    it('returns true for ApiError with status 503 (service unavailable)', () => {
      const error = new ApiError(503, 'Service unavailable');
      expect(shouldRetry(error)).toBe(true);
    });

    it('returns true for ApiError with status 502 (bad gateway)', () => {
      const error = new ApiError(502, 'Bad gateway');
      expect(shouldRetry(error)).toBe(true);
    });

    it('returns true for ApiError with status 504 (gateway timeout)', () => {
      const error = new ApiError(504, 'Gateway timeout');
      expect(shouldRetry(error)).toBe(true);
    });

    it('returns false for ApiError with status 400', () => {
      const error = new ApiError(400, 'Bad request');
      expect(shouldRetry(error)).toBe(false);
    });

    it('returns false for ApiError with status 404', () => {
      const error = new ApiError(404, 'Not found');
      expect(shouldRetry(error)).toBe(false);
    });

    it('returns false for ApiError with status 500 (internal server error)', () => {
      const error = new ApiError(500, 'Internal server error');
      expect(shouldRetry(error)).toBe(false);
    });

    it('returns true for TimeoutError', () => {
      const error = new TimeoutError(30000);
      expect(shouldRetry(error)).toBe(true);
    });

    it('returns false for generic Error', () => {
      const error = new Error('Something went wrong');
      expect(shouldRetry(error)).toBe(false);
    });

    it('returns false for null/undefined', () => {
      expect(shouldRetry(null)).toBe(false);
      expect(shouldRetry(undefined)).toBe(false);
    });
  });

  describe('handleApiError', () => {
    it('shows error toast for ApiError with error_code', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        error_code: ErrorCode.CAMERA_NOT_FOUND,
      };
      const error = new ApiError(404, 'Camera not found', undefined, problemDetails);

      const config = handleApiError(error);

      expect(toast.error).toHaveBeenCalledWith('Camera not found', expect.any(Object));
      expect(config.message).toBe('Camera not found');
      expect(config.variant).toBe('error');
      expect(config.retryable).toBe(false);
    });

    it('shows warning toast for validation errors', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Validation Error',
        status: 422,
        error_code: ErrorCode.VALIDATION_ERROR,
      };
      const error = new ApiError(422, 'Validation failed', undefined, problemDetails);

      const config = handleApiError(error);

      expect(toast.warning).toHaveBeenCalledWith('Invalid request data', expect.any(Object));
      expect(config.variant).toBe('warning');
    });

    it('shows warning toast for retryable errors', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Service Unavailable',
        status: 503,
        error_code: ErrorCode.SERVICE_UNAVAILABLE,
      };
      const error = new ApiError(503, 'Service unavailable', undefined, problemDetails);

      const config = handleApiError(error);

      expect(toast.warning).toHaveBeenCalledWith(
        'Service temporarily unavailable',
        expect.any(Object)
      );
      expect(config.retryable).toBe(true);
    });

    it('includes description with backend detail message', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        detail: 'Camera with ID "front_door" not found in database',
        error_code: ErrorCode.CAMERA_NOT_FOUND,
      };
      const error = new ApiError(404, 'Camera not found', undefined, problemDetails);

      handleApiError(error);

      expect(toast.error).toHaveBeenCalledWith(
        'Camera not found',
        expect.objectContaining({
          description: 'Camera with ID "front_door" not found in database',
        })
      );
    });

    it('handles ApiError without problemDetails', () => {
      const error = new ApiError(500, 'Internal server error');

      const config = handleApiError(error);

      expect(toast.error).toHaveBeenCalledWith('An unexpected error occurred', expect.any(Object));
      expect(config.message).toBe('An unexpected error occurred');
    });

    it('handles TimeoutError', () => {
      const error = new TimeoutError(30000);

      const config = handleApiError(error);

      expect(toast.warning).toHaveBeenCalledWith('Request timed out', expect.any(Object));
      expect(config.message).toBe('Request timed out');
      expect(config.retryable).toBe(true);
    });

    it('handles generic Error', () => {
      const error = new Error('Something went wrong');

      const config = handleApiError(error);

      expect(toast.error).toHaveBeenCalledWith('An unexpected error occurred', expect.any(Object));
      expect(config.message).toBe('An unexpected error occurred');
    });

    it('handles non-Error objects', () => {
      const error = 'string error';

      const config = handleApiError(error);

      expect(toast.error).toHaveBeenCalledWith('An unexpected error occurred', expect.any(Object));
      expect(config.message).toBe('An unexpected error occurred');
    });

    it('returns config with custom action when provided in error details', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Rate Limited',
        status: 429,
        error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
        retry_after: 60,
      };
      const error = new ApiError(429, 'Rate limited', undefined, problemDetails);

      const config = handleApiError(error);

      expect(config.retryable).toBe(true);
      expect(config.retryAfter).toBe(60);
    });
  });

  describe('ErrorConfig interface', () => {
    it('enforces correct ToastVariant types', () => {
      // This test validates TypeScript types at compile time
      const errorConfig: ErrorConfig = {
        message: 'Test message',
        variant: 'error',
        retryable: false,
      };

      const warningConfig: ErrorConfig = {
        message: 'Test message',
        variant: 'warning',
        retryable: true,
      };

      const infoConfig: ErrorConfig = {
        message: 'Test message',
        variant: 'info',
        retryable: false,
      };

      expect(errorConfig.variant).toBe('error');
      expect(warningConfig.variant).toBe('warning');
      expect(infoConfig.variant).toBe('info');
    });

    it('supports optional retryAfter field', () => {
      const configWithRetry: ErrorConfig = {
        message: 'Rate limited',
        variant: 'warning',
        retryable: true,
        retryAfter: 60,
      };

      expect(configWithRetry.retryAfter).toBe(60);
    });
  });
});
