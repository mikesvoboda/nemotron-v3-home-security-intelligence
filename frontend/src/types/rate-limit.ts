/**
 * Rate Limit Types
 *
 * Types for rate limit information extracted from API response headers.
 * The RateLimitInfo type is re-exported from the rate-limit-store for convenience.
 *
 * @see frontend/src/stores/rate-limit-store.ts - The Zustand store for rate limit state
 */

// Import RateLimitInfo for use in this file
import type { RateLimitInfo } from '../stores/rate-limit-store';

// Re-export RateLimitInfo for consumers of this module
export type { RateLimitInfo };

/**
 * API response wrapper that includes optional rate limit information.
 * Used when the caller needs access to both the response data and rate limit headers.
 *
 * @template T - The type of the response data
 *
 * @example
 * ```typescript
 * const response: ApiResponse<Event[]> = {
 *   data: events,
 *   rateLimit: {
 *     limit: 100,
 *     remaining: 95,
 *     reset: 1704067200,
 *   },
 * };
 * ```
 */
export interface ApiResponse<T> {
  /** The response data from the API */
  data: T;
  /** Rate limit information extracted from response headers, if present */
  rateLimit?: RateLimitInfo;
}
