/**
 * Tests for QueryClient retry configuration (NEM-1962)
 *
 * Tests the automatic retry logic for transient errors with:
 * - Exponential backoff (1s, 2s, 4s)
 * - Respect for Retry-After header
 * - Smart retry based on error type
 * - Mutation-safe retry (only TIMEOUT for mutations)
 */

import { describe, it, expect } from 'vitest';

import { ApiError, type ProblemDetails, TimeoutError } from './api';
import {
  createQueryClient,
  calculateRetryDelay,
  shouldRetryQuery,
  shouldRetryMutation,
  MAX_RETRY_ATTEMPTS,
  RETRY_BASE_DELAY_MS,
  MAX_RETRY_DELAY_MS,
} from './queryClient';
import { ErrorCode } from '../utils/error-handling';

describe('QueryClient retry configuration', () => {
  describe('retry constants', () => {
    it('exports MAX_RETRY_ATTEMPTS as 3', () => {
      expect(MAX_RETRY_ATTEMPTS).toBe(3);
    });

    it('exports RETRY_BASE_DELAY_MS as 1000 (1 second)', () => {
      expect(RETRY_BASE_DELAY_MS).toBe(1000);
    });

    it('exports MAX_RETRY_DELAY_MS as 30000 (30 seconds)', () => {
      expect(MAX_RETRY_DELAY_MS).toBe(30000);
    });
  });

  describe('calculateRetryDelay', () => {
    describe('exponential backoff', () => {
      it('returns 1 second (1000ms) for first retry attempt (attemptIndex=0)', () => {
        const error = new ApiError(503, 'Service Unavailable');
        const delay = calculateRetryDelay(0, error);
        expect(delay).toBe(1000);
      });

      it('returns 2 seconds (2000ms) for second retry attempt (attemptIndex=1)', () => {
        const error = new ApiError(503, 'Service Unavailable');
        const delay = calculateRetryDelay(1, error);
        expect(delay).toBe(2000);
      });

      it('returns 4 seconds (4000ms) for third retry attempt (attemptIndex=2)', () => {
        const error = new ApiError(503, 'Service Unavailable');
        const delay = calculateRetryDelay(2, error);
        expect(delay).toBe(4000);
      });

      it('caps delay at MAX_RETRY_DELAY_MS for high attempt indices', () => {
        const error = new ApiError(503, 'Service Unavailable');
        // 2^10 * 1000 = 1,024,000 which exceeds 30,000
        const delay = calculateRetryDelay(10, error);
        expect(delay).toBe(MAX_RETRY_DELAY_MS);
      });
    });

    describe('Retry-After header respect', () => {
      it('uses retry_after from problemDetails when present (seconds)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Rate Limited',
          status: 429,
          error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
          retry_after: 15, // 15 seconds
        };
        const error = new ApiError(429, 'Rate limited', undefined, problemDetails);

        const delay = calculateRetryDelay(0, error);
        expect(delay).toBe(15000); // 15 seconds in ms
      });

      it('uses retry_after even when it is longer than exponential backoff', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Rate Limited',
          status: 429,
          error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
          retry_after: 20, // 20 seconds (within MAX_RETRY_DELAY_MS of 30s)
        };
        const error = new ApiError(429, 'Rate limited', undefined, problemDetails);

        // First attempt would normally be 1s, but Retry-After says 20s
        const delay = calculateRetryDelay(0, error);
        expect(delay).toBe(20000);
      });

      it('caps retry_after at MAX_RETRY_DELAY_MS', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Rate Limited',
          status: 429,
          error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
          retry_after: 300, // 300 seconds = 5 minutes
        };
        const error = new ApiError(429, 'Rate limited', undefined, problemDetails);

        const delay = calculateRetryDelay(0, error);
        expect(delay).toBe(MAX_RETRY_DELAY_MS); // Capped at 30s
      });

      it('falls back to exponential backoff when retry_after is not present', () => {
        const error = new ApiError(503, 'Service Unavailable');
        const delay = calculateRetryDelay(1, error);
        expect(delay).toBe(2000); // Standard exponential: 2^1 * 1000
      });

      it('ignores invalid retry_after values (negative)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Rate Limited',
          status: 429,
          error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
          retry_after: -10,
        };
        const error = new ApiError(429, 'Rate limited', undefined, problemDetails);

        const delay = calculateRetryDelay(0, error);
        expect(delay).toBe(1000); // Falls back to exponential
      });

      it('ignores non-numeric retry_after values', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Rate Limited',
          status: 429,
          error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
          retry_after: 'invalid' as unknown as number,
        };
        const error = new ApiError(429, 'Rate limited', undefined, problemDetails);

        const delay = calculateRetryDelay(0, error);
        expect(delay).toBe(1000); // Falls back to exponential
      });
    });

    describe('non-ApiError handling', () => {
      it('handles TimeoutError with exponential backoff', () => {
        const error = new TimeoutError(30000);
        const delay = calculateRetryDelay(1, error);
        expect(delay).toBe(2000);
      });

      it('handles generic Error with exponential backoff', () => {
        const error = new Error('Network error');
        const delay = calculateRetryDelay(0, error);
        expect(delay).toBe(1000);
      });
    });
  });

  describe('shouldRetryQuery', () => {
    describe('retryable errors', () => {
      it('returns true for SERVICE_UNAVAILABLE (503)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Service Unavailable',
          status: 503,
          error_code: ErrorCode.SERVICE_UNAVAILABLE,
        };
        const error = new ApiError(503, 'Service Unavailable', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(true);
      });

      it('returns true for RATE_LIMIT_EXCEEDED (429)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Rate Limited',
          status: 429,
          error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
        };
        const error = new ApiError(429, 'Rate limited', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(true);
      });

      it('returns true for TIMEOUT', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Timeout',
          status: 504,
          error_code: ErrorCode.TIMEOUT,
        };
        const error = new ApiError(504, 'Timeout', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(true);
      });

      it('returns true for TimeoutError', () => {
        const error = new TimeoutError(30000);
        expect(shouldRetryQuery(0, error)).toBe(true);
      });

      it('returns true for AI service unavailable errors', () => {
        const codes = [
          ErrorCode.DETECTOR_UNAVAILABLE,
          ErrorCode.RTDETR_UNAVAILABLE,
          ErrorCode.NEMOTRON_UNAVAILABLE,
          ErrorCode.AI_SERVICE_TIMEOUT,
        ];

        for (const code of codes) {
          const problemDetails: ProblemDetails = {
            type: 'about:blank',
            title: 'AI Service Error',
            status: 503,
            error_code: code,
          };
          const error = new ApiError(503, 'AI Service Error', undefined, problemDetails);
          expect(shouldRetryQuery(0, error)).toBe(true);
        }
      });

      it('returns true for retryable HTTP status codes without error_code', () => {
        // 429, 502, 503, 504 are all retryable
        const statuses = [429, 502, 503, 504];
        for (const status of statuses) {
          const error = new ApiError(status, 'Error');
          expect(shouldRetryQuery(0, error)).toBe(true);
        }
      });
    });

    describe('non-retryable errors', () => {
      it('returns false for CAMERA_NOT_FOUND (404)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Not Found',
          status: 404,
          error_code: ErrorCode.CAMERA_NOT_FOUND,
        };
        const error = new ApiError(404, 'Camera not found', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(false);
      });

      it('returns false for VALIDATION_ERROR (400)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          error_code: ErrorCode.VALIDATION_ERROR,
        };
        const error = new ApiError(400, 'Validation error', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(false);
      });

      it('returns false for AUTHENTICATION_REQUIRED (401)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Unauthorized',
          status: 401,
          error_code: ErrorCode.AUTHENTICATION_REQUIRED,
        };
        const error = new ApiError(401, 'Unauthorized', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(false);
      });

      it('returns false for ACCESS_DENIED (403)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Forbidden',
          status: 403,
          error_code: ErrorCode.ACCESS_DENIED,
        };
        const error = new ApiError(403, 'Forbidden', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(false);
      });

      it('returns false for INTERNAL_ERROR (500)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Internal Error',
          status: 500,
          error_code: ErrorCode.INTERNAL_ERROR,
        };
        const error = new ApiError(500, 'Internal error', undefined, problemDetails);
        expect(shouldRetryQuery(0, error)).toBe(false);
      });

      it('returns false for generic Error (not ApiError or TimeoutError)', () => {
        const error = new Error('Something went wrong');
        expect(shouldRetryQuery(0, error)).toBe(false);
      });
    });

    describe('attempt limit', () => {
      it('returns false when failureCount exceeds MAX_RETRY_ATTEMPTS', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Service Unavailable',
          status: 503,
          error_code: ErrorCode.SERVICE_UNAVAILABLE,
        };
        const error = new ApiError(503, 'Service Unavailable', undefined, problemDetails);

        // Max is 3, so attemptIndex 0, 1, 2 are valid (3 attempts total)
        expect(shouldRetryQuery(0, error)).toBe(true);
        expect(shouldRetryQuery(1, error)).toBe(true);
        expect(shouldRetryQuery(2, error)).toBe(true);
        expect(shouldRetryQuery(3, error)).toBe(false); // 4th attempt, should not retry
      });
    });
  });

  describe('shouldRetryMutation', () => {
    describe('safe retry for mutations (TIMEOUT only)', () => {
      it('returns true for TimeoutError', () => {
        const error = new TimeoutError(30000);
        expect(shouldRetryMutation(0, error)).toBe(true);
      });

      it('returns true for TIMEOUT error code', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Timeout',
          status: 504,
          error_code: ErrorCode.TIMEOUT,
        };
        const error = new ApiError(504, 'Timeout', undefined, problemDetails);
        expect(shouldRetryMutation(0, error)).toBe(true);
      });

      it('returns true for OPERATION_TIMEOUT error code', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Operation Timeout',
          status: 504,
          error_code: ErrorCode.OPERATION_TIMEOUT,
        };
        const error = new ApiError(504, 'Operation Timeout', undefined, problemDetails);
        expect(shouldRetryMutation(0, error)).toBe(true);
      });

      it('returns true for AI_SERVICE_TIMEOUT error code', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'AI Service Timeout',
          status: 504,
          error_code: ErrorCode.AI_SERVICE_TIMEOUT,
        };
        const error = new ApiError(504, 'AI Service Timeout', undefined, problemDetails);
        expect(shouldRetryMutation(0, error)).toBe(true);
      });
    });

    describe('non-retryable mutations', () => {
      it('returns false for SERVICE_UNAVAILABLE (could cause duplicate side effects)', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Service Unavailable',
          status: 503,
          error_code: ErrorCode.SERVICE_UNAVAILABLE,
        };
        const error = new ApiError(503, 'Service Unavailable', undefined, problemDetails);
        expect(shouldRetryMutation(0, error)).toBe(false);
      });

      it('returns false for RATE_LIMIT_EXCEEDED', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Rate Limited',
          status: 429,
          error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
        };
        const error = new ApiError(429, 'Rate limited', undefined, problemDetails);
        expect(shouldRetryMutation(0, error)).toBe(false);
      });

      it('returns false for DATABASE_ERROR', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Database Error',
          status: 500,
          error_code: ErrorCode.DATABASE_ERROR,
        };
        const error = new ApiError(500, 'Database error', undefined, problemDetails);
        expect(shouldRetryMutation(0, error)).toBe(false);
      });

      it('returns false for validation errors', () => {
        const problemDetails: ProblemDetails = {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          error_code: ErrorCode.VALIDATION_ERROR,
        };
        const error = new ApiError(400, 'Validation error', undefined, problemDetails);
        expect(shouldRetryMutation(0, error)).toBe(false);
      });

      it('returns false for generic Error', () => {
        const error = new Error('Something went wrong');
        expect(shouldRetryMutation(0, error)).toBe(false);
      });
    });

    describe('attempt limit for mutations', () => {
      it('returns false when failureCount exceeds MAX_RETRY_ATTEMPTS', () => {
        const error = new TimeoutError(30000);

        expect(shouldRetryMutation(0, error)).toBe(true);
        expect(shouldRetryMutation(1, error)).toBe(true);
        expect(shouldRetryMutation(2, error)).toBe(true);
        expect(shouldRetryMutation(3, error)).toBe(false); // 4th attempt, should not retry
      });
    });
  });

  describe('QueryClient integration', () => {
    it('uses shouldRetryQuery for query retry configuration', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();

      // Verify retry is configured as a function
      expect(typeof options.queries?.retry).toBe('function');
    });

    it('uses calculateRetryDelay for retryDelay configuration', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();

      // Verify retryDelay is configured as a function
      expect(typeof options.queries?.retryDelay).toBe('function');
    });

    it('uses shouldRetryMutation for mutation retry configuration', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();

      // Verify mutation retry is configured as a function
      expect(typeof options.mutations?.retry).toBe('function');
    });
  });
});
