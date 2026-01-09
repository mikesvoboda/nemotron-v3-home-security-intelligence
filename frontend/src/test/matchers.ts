/**
 * Custom assertion helpers and matchers.
 *
 * This module provides domain-specific assertions that make tests more
 * readable and expressive. These helpers reduce boilerplate and encode
 * business logic expectations.
 *
 * ## Usage
 *
 * ### Risk Level Assertions
 *
 * ```typescript
 * import { expectRiskLevel } from '@/test/matchers';
 *
 * expectRiskLevel(25).toBeLow();
 * expectRiskLevel(85).toBeHigh();
 * ```
 *
 * ### API Response Assertions
 *
 * ```typescript
 * import { expectApiSuccess, expectApiError } from '@/test/matchers';
 *
 * expectApiSuccess(response, 200);
 * expectApiError(response, 404, 'Not found');
 * ```
 *
 * ### Data Structure Assertions
 *
 * ```typescript
 * import { expectValidCamera, expectValidEvent } from '@/test/matchers';
 *
 * expectValidCamera(camera);
 * expectValidEvent(event);
 * ```
 *
 * @module test/matchers
 */

import { expect } from 'vitest';

import type { Camera, Event, Detection } from '@/services/api';

// ============================================================================
// Risk Level Assertions
// ============================================================================

/**
 * Assertion helpers for risk levels.
 *
 * @param score - Risk score (0-100)
 * @returns Assertion object with helper methods
 *
 * @example
 * ```typescript
 * expectRiskLevel(25).toBeLow();
 * expectRiskLevel(50).toBeMedium();
 * expectRiskLevel(85).toBeHigh();
 * ```
 */
export function expectRiskLevel(score: number) {
  return {
    toBeLow() {
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThan(30);
    },
    toBeMedium() {
      expect(score).toBeGreaterThanOrEqual(30);
      expect(score).toBeLessThan(70);
    },
    toBeHigh() {
      expect(score).toBeGreaterThanOrEqual(70);
      expect(score).toBeLessThanOrEqual(100);
    },
    toBeValid() {
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);
    },
  };
}

// ============================================================================
// API Response Assertions
// ============================================================================

/**
 * Assert that a response represents a successful API call.
 *
 * @param response - Response object
 * @param expectedStatus - Expected status code (default: 200)
 *
 * @example
 * ```typescript
 * const response = await api.getCameras();
 * expectApiSuccess(response, 200);
 * ```
 */
export function expectApiSuccess(response: Response, expectedStatus = 200) {
  expect(response.ok).toBe(true);
  expect(response.status).toBe(expectedStatus);
}

/**
 * Assert that a response represents a failed API call.
 *
 * @param response - Response object
 * @param expectedStatus - Expected error status code
 * @param errorMessage - Optional expected error message
 *
 * @example
 * ```typescript
 * const response = await api.getCamera('nonexistent');
 * expectApiError(response, 404, 'Camera not found');
 * ```
 */
export function expectApiError(
  response: Response,
  expectedStatus: number,
  errorMessage?: string
) {
  expect(response.ok).toBe(false);
  expect(response.status).toBe(expectedStatus);

  if (errorMessage) {
    void response.json().then((data) => {
      expect(data.detail).toContain(errorMessage);
    });
  }
}

// ============================================================================
// Data Structure Assertions
// ============================================================================

/**
 * Assert that an object is a valid Camera.
 *
 * @param camera - Camera object to validate
 *
 * @example
 * ```typescript
 * const camera = await api.getCamera('front-door');
 * expectValidCamera(camera);
 * ```
 */
export function expectValidCamera(camera: unknown): asserts camera is Camera {
  expect(camera).toBeDefined();
  expect(camera).toHaveProperty('id');
  expect(camera).toHaveProperty('name');
  expect(camera).toHaveProperty('folder_path');
  expect(camera).toHaveProperty('status');
  expect(camera).toHaveProperty('created_at');
  expect(camera).toHaveProperty('last_seen_at');

  const c = camera as Camera;
  expect(typeof c.id).toBe('string');
  expect(typeof c.name).toBe('string');
  expect(['online', 'offline', 'error']).toContain(c.status);
}

/**
 * Assert that an object is a valid Event.
 *
 * @param event - Event object to validate
 *
 * @example
 * ```typescript
 * const event = await api.getEvent(123);
 * expectValidEvent(event);
 * ```
 */
export function expectValidEvent(event: unknown): asserts event is Event {
  expect(event).toBeDefined();
  expect(event).toHaveProperty('id');
  expect(event).toHaveProperty('camera_id');
  expect(event).toHaveProperty('started_at');
  expect(event).toHaveProperty('risk_score');
  expect(event).toHaveProperty('risk_level');
  expect(event).toHaveProperty('summary');

  const e = event as Event;
  expect(typeof e.id).toBe('number');
  expect(typeof e.camera_id).toBe('string');
  expect(['low', 'medium', 'high']).toContain(e.risk_level);
  if (e.risk_score !== null && e.risk_score !== undefined) {
    expectRiskLevel(e.risk_score).toBeValid();
  }
}

/**
 * Assert that an object is a valid Detection.
 *
 * @param detection - Detection object to validate
 *
 * @example
 * ```typescript
 * const detection = await api.getDetection(456);
 * expectValidDetection(detection);
 * ```
 */
export function expectValidDetection(
  detection: unknown
): asserts detection is Detection {
  expect(detection).toBeDefined();
  expect(detection).toHaveProperty('id');
  expect(detection).toHaveProperty('camera_id');
  expect(detection).toHaveProperty('object_type');
  expect(detection).toHaveProperty('confidence');

  const d = detection as Detection;
  expect(typeof d.id).toBe('number');
  expect(typeof d.object_type).toBe('string');
  if (d.confidence !== null && d.confidence !== undefined) {
    expect(d.confidence).toBeGreaterThanOrEqual(0);
    expect(d.confidence).toBeLessThanOrEqual(1);
  }
}

// ============================================================================
// Bounding Box Assertions
// ============================================================================

/**
 * Assert that a bounding box is valid.
 *
 * @param bbox - Bounding box [x1, y1, x2, y2]
 *
 * @example
 * ```typescript
 * expectValidBoundingBox([100, 100, 200, 200]);
 * ```
 */
export function expectValidBoundingBox(bbox: number[]) {
  expect(Array.isArray(bbox)).toBe(true);
  expect(bbox).toHaveLength(4);

  const [x1, y1, x2, y2] = bbox;
  expect(x1).toBeLessThan(x2);
  expect(y1).toBeLessThan(y2);
  expect(x1).toBeGreaterThanOrEqual(0);
  expect(y1).toBeGreaterThanOrEqual(0);
}

// ============================================================================
// Timestamp Assertions
// ============================================================================

/**
 * Assert that a timestamp is recent (within the last N seconds).
 *
 * @param timestamp - ISO timestamp string
 * @param maxAgeSeconds - Maximum age in seconds (default: 60)
 *
 * @example
 * ```typescript
 * expectRecentTimestamp(event.started_at, 30);
 * ```
 */
export function expectRecentTimestamp(
  timestamp: string,
  maxAgeSeconds = 60
) {
  const date = new Date(timestamp);
  const now = new Date();
  const ageSeconds = (now.getTime() - date.getTime()) / 1000;

  expect(ageSeconds).toBeLessThanOrEqual(maxAgeSeconds);
  expect(ageSeconds).toBeGreaterThanOrEqual(0);
}

/**
 * Assert that a timestamp is in the past.
 *
 * @param timestamp - ISO timestamp string
 *
 * @example
 * ```typescript
 * expectPastTimestamp(event.ended_at);
 * ```
 */
export function expectPastTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  const now = new Date();
  expect(date.getTime()).toBeLessThanOrEqual(now.getTime());
}

/**
 * Assert that timestamp1 is before timestamp2.
 *
 * @param timestamp1 - First timestamp
 * @param timestamp2 - Second timestamp
 *
 * @example
 * ```typescript
 * expectTimestampBefore(event.started_at, event.ended_at);
 * ```
 */
export function expectTimestampBefore(timestamp1: string, timestamp2: string) {
  const date1 = new Date(timestamp1);
  const date2 = new Date(timestamp2);
  expect(date1.getTime()).toBeLessThan(date2.getTime());
}

// ============================================================================
// Array Assertions
// ============================================================================

/**
 * Assert that an array is sorted by a specific field.
 *
 * @param array - Array to check
 * @param field - Field to check sorting on
 * @param order - Sort order ('asc' or 'desc')
 *
 * @example
 * ```typescript
 * expectSortedBy(events, 'started_at', 'desc');
 * ```
 */
export function expectSortedBy<T extends Record<string, unknown>>(
  array: T[],
  field: keyof T,
  order: 'asc' | 'desc' = 'asc'
) {
  for (let i = 0; i < array.length - 1; i++) {
    const current = array[i][field] as number | string;
    const next = array[i + 1][field] as number | string;

    if (order === 'asc') {
      expect(current <= next).toBe(true);
    } else {
      expect(current >= next).toBe(true);
    }
  }
}

/**
 * Assert that an array contains unique values for a specific field.
 *
 * @param array - Array to check
 * @param field - Field to check uniqueness on
 *
 * @example
 * ```typescript
 * expectUniqueBy(cameras, 'id');
 * ```
 */
export function expectUniqueBy<T>(array: T[], field: keyof T) {
  const values = array.map((item) => item[field]);
  const uniqueValues = new Set(values);
  expect(uniqueValues.size).toBe(values.length);
}

// ============================================================================
// Loading State Assertions
// ============================================================================

/**
 * Assert that a query result is in loading state.
 *
 * @param result - Query result object
 *
 * @example
 * ```typescript
 * expectLoading(query);
 * ```
 */
export function expectLoading(result: { isLoading: boolean; data?: unknown }) {
  expect(result.isLoading).toBe(true);
  expect(result.data).toBeUndefined();
}

/**
 * Assert that a query result has loaded successfully.
 *
 * @param result - Query result object
 *
 * @example
 * ```typescript
 * expectLoaded(query);
 * expect(query.data).toBeDefined();
 * ```
 */
export function expectLoaded(result: { isLoading: boolean; data?: unknown }) {
  expect(result.isLoading).toBe(false);
  expect(result.data).toBeDefined();
}

/**
 * Assert that a query result has an error.
 *
 * @param result - Query result object
 * @param expectedError - Optional expected error message
 *
 * @example
 * ```typescript
 * expectError(query, 'Failed to fetch');
 * ```
 */
export function expectError(
  result: { isLoading: boolean; error: Error | null },
  expectedError?: string
) {
  expect(result.isLoading).toBe(false);
  expect(result.error).not.toBeNull();
  expect(result.error).toBeDefined();

  if (expectedError) {
    expect(result.error?.message).toContain(expectedError);
  }
}
