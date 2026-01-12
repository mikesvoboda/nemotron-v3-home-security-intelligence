/**
 * Rate Limit Types Tests
 *
 * Tests for the RateLimitInfo and ApiResponse type definitions.
 * These tests verify type correctness and runtime behavior of rate limit types.
 */

import { describe, expect, it } from 'vitest';

import type { ApiResponse, RateLimitInfo } from './rate-limit';

describe('rate-limit types', () => {
  describe('RateLimitInfo', () => {
    it('allows creating a valid RateLimitInfo object with required fields', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 95,
        reset: 1704067200,
      };

      expect(info.limit).toBe(100);
      expect(info.remaining).toBe(95);
      expect(info.reset).toBe(1704067200);
      expect(info.retryAfter).toBeUndefined();
    });

    it('allows creating a RateLimitInfo object with optional retryAfter', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: 1704067200,
        retryAfter: 60,
      };

      expect(info.limit).toBe(100);
      expect(info.remaining).toBe(0);
      expect(info.reset).toBe(1704067200);
      expect(info.retryAfter).toBe(60);
    });

    it('handles zero values correctly', () => {
      const info: RateLimitInfo = {
        limit: 0,
        remaining: 0,
        reset: 0,
      };

      expect(info.limit).toBe(0);
      expect(info.remaining).toBe(0);
      expect(info.reset).toBe(0);
    });

    it('handles large limit values', () => {
      const info: RateLimitInfo = {
        limit: 10000,
        remaining: 9999,
        reset: 2000000000,
      };

      expect(info.limit).toBe(10000);
      expect(info.remaining).toBe(9999);
      expect(info.reset).toBe(2000000000);
    });
  });

  describe('ApiResponse', () => {
    it('allows creating a response with data only', () => {
      interface TestData {
        id: string;
        name: string;
      }

      const response: ApiResponse<TestData> = {
        data: { id: '123', name: 'Test' },
      };

      expect(response.data).toEqual({ id: '123', name: 'Test' });
      expect(response.rateLimit).toBeUndefined();
    });

    it('allows creating a response with data and rate limit info', () => {
      interface TestData {
        items: string[];
      }

      const response: ApiResponse<TestData> = {
        data: { items: ['a', 'b', 'c'] },
        rateLimit: {
          limit: 100,
          remaining: 95,
          reset: 1704067200,
        },
      };

      expect(response.data).toEqual({ items: ['a', 'b', 'c'] });
      expect(response.rateLimit).toEqual({
        limit: 100,
        remaining: 95,
        reset: 1704067200,
      });
    });

    it('allows creating a response with primitive data type', () => {
      const response: ApiResponse<number> = {
        data: 42,
        rateLimit: {
          limit: 50,
          remaining: 49,
          reset: 1704067200,
        },
      };

      expect(response.data).toBe(42);
      expect(response.rateLimit?.limit).toBe(50);
    });

    it('allows creating a response with array data type', () => {
      const response: ApiResponse<string[]> = {
        data: ['item1', 'item2'],
        rateLimit: {
          limit: 100,
          remaining: 98,
          reset: 1704067200,
          retryAfter: 30,
        },
      };

      expect(response.data).toEqual(['item1', 'item2']);
      expect(response.rateLimit?.retryAfter).toBe(30);
    });

    it('allows creating a response with null data', () => {
      const response: ApiResponse<null> = {
        data: null,
      };

      expect(response.data).toBeNull();
    });

    it('allows creating a response with undefined rate limit', () => {
      const response: ApiResponse<{ value: boolean }> = {
        data: { value: true },
        rateLimit: undefined,
      };

      expect(response.data.value).toBe(true);
      expect(response.rateLimit).toBeUndefined();
    });

    it('allows accessing nested rate limit properties', () => {
      interface ComplexData {
        nested: {
          value: number;
        };
      }

      const response: ApiResponse<ComplexData> = {
        data: { nested: { value: 100 } },
        rateLimit: {
          limit: 1000,
          remaining: 500,
          reset: 1704067200,
        },
      };

      expect(response.data.nested.value).toBe(100);
      expect(response.rateLimit?.remaining).toBe(500);
      expect((response.rateLimit?.limit ?? 0) - (response.rateLimit?.remaining ?? 0)).toBe(500);
    });
  });

  describe('type safety', () => {
    it('maintains type safety for rate limit info usage calculations', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 25,
        reset: 1704067200,
      };

      // Calculate usage percentage
      const used = info.limit - info.remaining;
      const usagePercent = (used / info.limit) * 100;

      expect(used).toBe(75);
      expect(usagePercent).toBe(75);
    });

    it('maintains type safety for reset time calculations', () => {
      const now = Math.floor(Date.now() / 1000);
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: now + 60,
      };

      // Calculate seconds until reset
      const secondsUntilReset = info.reset - now;

      expect(secondsUntilReset).toBe(60);
    });

    it('handles optional retryAfter in calculations', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: 1704067200,
        retryAfter: 30,
      };

      // Use nullish coalescing for optional property
      const waitTime = info.retryAfter ?? 0;

      expect(waitTime).toBe(30);
    });

    it('handles missing retryAfter in calculations', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: 1704067200,
      };

      // Use nullish coalescing for optional property
      const waitTime = info.retryAfter ?? 0;

      expect(waitTime).toBe(0);
    });
  });

  describe('integration patterns', () => {
    it('supports extracting rate limit from ApiResponse', () => {
      interface EventData {
        id: string;
        type: string;
      }

      const response: ApiResponse<EventData[]> = {
        data: [
          { id: '1', type: 'motion' },
          { id: '2', type: 'person' },
        ],
        rateLimit: {
          limit: 100,
          remaining: 98,
          reset: 1704067200,
        },
      };

      // Extract data and rate limit separately
      const { data, rateLimit } = response;

      expect(data).toHaveLength(2);
      expect(rateLimit?.remaining).toBe(98);
    });

    it('supports conditional rate limit checking', () => {
      const responseWithLimit: ApiResponse<string> = {
        data: 'success',
        rateLimit: {
          limit: 100,
          remaining: 0,
          reset: 1704067200,
        },
      };

      const responseWithoutLimit: ApiResponse<string> = {
        data: 'success',
      };

      // Check if rate limited
      const isLimited1 = responseWithLimit.rateLimit?.remaining === 0;
      const isLimited2 = responseWithoutLimit.rateLimit?.remaining === 0;

      expect(isLimited1).toBe(true);
      expect(isLimited2).toBe(false);
    });

    it('supports rate limit info serialization', () => {
      const info: RateLimitInfo = {
        limit: 100,
        remaining: 50,
        reset: 1704067200,
        retryAfter: 30,
      };

      // Serialize and deserialize
      const serialized = JSON.stringify(info);
      const deserialized = JSON.parse(serialized) as RateLimitInfo;

      expect(deserialized).toEqual(info);
    });

    it('supports ApiResponse serialization', () => {
      const response: ApiResponse<{ status: string }> = {
        data: { status: 'ok' },
        rateLimit: {
          limit: 100,
          remaining: 99,
          reset: 1704067200,
        },
      };

      // Serialize and deserialize
      const serialized = JSON.stringify(response);
      const deserialized = JSON.parse(serialized) as ApiResponse<{ status: string }>;

      expect(deserialized.data.status).toBe('ok');
      expect(deserialized.rateLimit?.remaining).toBe(99);
    });
  });
});
