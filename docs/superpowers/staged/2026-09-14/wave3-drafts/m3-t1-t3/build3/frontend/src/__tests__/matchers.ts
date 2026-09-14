/**
 * Domain-specific custom Vitest matchers for frontend tests.
 *
 * This module extends Vitest's expect API with custom matchers for validating
 * common domain objects in the home security monitoring system. These matchers
 * improve test readability and provide clear, consistent error messages.
 *
 * @example
 * ```ts
 * import { expect } from 'vitest';
 * import './matchers'; // Import to register matchers
 *
 * test('camera validation', () => {
 *   const camera = { id: 'front_door', name: 'Front Door', ... };
 *   expect(camera).toBeValidCamera();
 * });
 * ```
 */

import { expect } from 'vitest';

import type { RiskLevel } from '../types/constants';

/**
 * Camera validation interface for type safety.
 */
interface Camera {
  id: string;
  name: string;
  folder_path: string;
  status: string;
  created_at: string;
  last_seen_at?: string | null;
}

/**
 * Event validation interface for type safety.
 */
interface Event {
  id: number;
  camera_id: string;
  started_at: string;
  ended_at?: string | null;
  risk_score?: number | null;
  risk_level?: string | null;
  summary?: string | null;
  reasoning?: string | null;
  reviewed?: boolean;
  detection_count?: number;
  detection_ids?: number[];
}

/**
 * Detection validation interface for type safety.
 */
interface Detection {
  id: number;
  camera_id: string;
  file_path: string;
  detected_at: string;
  object_type?: string | null;
  confidence?: number | null;
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_width?: number | null;
  bbox_height?: number | null;
  media_type?: string | null;
  duration?: number | null;
}

/**
 * Custom matchers interface for TypeScript type augmentation.
 */
interface CustomMatchers<R = unknown> {
  /**
   * Assert that the object is a valid Camera.
   */
  toBeValidCamera(): R;

  /**
   * Assert that the object is a valid Event.
   */
  toBeValidEvent(): R;

  /**
   * Assert that the object is a valid Detection.
   */
  toBeValidDetection(): R;

  /**
   * Assert that the object has the expected risk level.
   * @param expected Expected risk level (low, medium, high, critical)
   */
  toHaveRiskLevel(expected: RiskLevel): R;

  /**
   * Assert that a numeric risk score is in the valid range (0-100).
   */
  toBeValidRiskScore(): R;

  /**
   * Assert that an HTML element is accessible (has proper ARIA attributes).
   */
  toBeAccessible(): R;

  /**
   * Assert that a date string is in valid ISO 8601 format.
   */
  toBeValidISODate(): R;

  /**
   * Assert that an object represents a valid paginated response.
   * @param collectionKey The key containing the data array (e.g., 'events', 'cameras')
   */
  toBeValidPaginatedResponse(collectionKey: string): R;

  /**
   * Assert that axe accessibility results have no violations.
   * Used with vitest-axe for accessibility testing.
   */
  toHaveNoViolations(): R;
}

// Augment Vitest's expect with custom matchers
declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-empty-object-type
  interface Assertion<T = any> extends CustomMatchers<T> {}
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends CustomMatchers {}
}

/**
 * Validate ISO 8601 date string format.
 */
function isValidISODate(dateString: unknown): boolean {
  if (typeof dateString !== 'string') return false;

  try {
    const date = new Date(dateString);
    // Check if the date is valid and the string matches ISO format
    return !isNaN(date.getTime()) && dateString === date.toISOString();
  } catch {
    return false;
  }
}

/**
 * Register custom matchers with Vitest.
 */
expect.extend({
  /**
   * Assert that the received value is a valid Camera object.
   */
  toBeValidCamera(received: unknown) {
    const camera = received as Camera;
    const { isNot } = this;

    // Type check
    if (typeof camera !== 'object' || camera === null) {
      return {
        pass: false,
        message: () => `Expected value to be an object, got ${typeof received}`,
      };
    }

    // Required field validations
    const errors: string[] = [];

    if (!camera.id || typeof camera.id !== 'string') {
      errors.push("Camera must have a non-empty 'id' string");
    }

    if (!camera.name || typeof camera.name !== 'string') {
      errors.push("Camera must have a non-empty 'name' string");
    }

    if (!camera.folder_path || typeof camera.folder_path !== 'string') {
      errors.push("Camera must have a non-empty 'folder_path' string");
    }

    const validStatuses = ['online', 'offline', 'error', 'unknown'];
    if (!camera.status || !validStatuses.includes(camera.status)) {
      errors.push(`Camera status must be one of ${validStatuses.join(', ')}`);
    }

    if (!camera.created_at || !isValidISODate(camera.created_at)) {
      errors.push('Camera must have a valid ISO 8601 created_at timestamp');
    }

    if (camera.last_seen_at !== null && camera.last_seen_at !== undefined) {
      if (!isValidISODate(camera.last_seen_at)) {
        errors.push('Camera last_seen_at must be a valid ISO 8601 timestamp or null');
      }
    }

    const pass = errors.length === 0;

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected camera not to be valid, but it is valid`;
        }
        return `Expected camera to be valid, but found errors:\n${errors.join('\n')}`;
      },
    };
  },

  /**
   * Assert that the received value is a valid Event object.
   */
  toBeValidEvent(received: unknown) {
    const event = received as Event;
    const { isNot } = this;

    if (typeof event !== 'object' || event === null) {
      return {
        pass: false,
        message: () => `Expected value to be an object, got ${typeof received}`,
      };
    }

    const errors: string[] = [];

    // Required fields
    if (!event.id || typeof event.id !== 'number' || event.id <= 0) {
      errors.push('Event must have a positive integer id');
    }

    if (!event.camera_id || typeof event.camera_id !== 'string') {
      errors.push("Event must have a non-empty 'camera_id' string");
    }

    if (!event.started_at || !isValidISODate(event.started_at)) {
      errors.push('Event must have a valid ISO 8601 started_at timestamp');
    }

    // Optional fields validation
    if (event.ended_at !== null && event.ended_at !== undefined) {
      if (!isValidISODate(event.ended_at)) {
        errors.push('Event ended_at must be a valid ISO 8601 timestamp or null');
      }
    }

    if (event.risk_score !== null && event.risk_score !== undefined) {
      if (typeof event.risk_score !== 'number' || event.risk_score < 0 || event.risk_score > 100) {
        errors.push('Event risk_score must be a number between 0 and 100 or null');
      }
    }

    if (event.risk_level !== null && event.risk_level !== undefined) {
      const validLevels = ['low', 'medium', 'high', 'critical'];
      if (!validLevels.includes(event.risk_level)) {
        errors.push(`Event risk_level must be one of ${validLevels.join(', ')} or null`);
      }
    }

    if (event.reviewed !== undefined && typeof event.reviewed !== 'boolean') {
      errors.push('Event reviewed must be a boolean');
    }

    if (event.detection_count !== undefined) {
      if (typeof event.detection_count !== 'number' || event.detection_count < 0) {
        errors.push('Event detection_count must be a non-negative number');
      }
    }

    if (event.detection_ids !== undefined) {
      if (!Array.isArray(event.detection_ids)) {
        errors.push('Event detection_ids must be an array');
      } else if (!event.detection_ids.every((id) => typeof id === 'number')) {
        errors.push('Event detection_ids must contain only numbers');
      }
    }

    const pass = errors.length === 0;

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected event not to be valid, but it is valid`;
        }
        return `Expected event to be valid, but found errors:\n${errors.join('\n')}`;
      },
    };
  },

  /**
   * Assert that the received value is a valid Detection object.
   */
  toBeValidDetection(received: unknown) {
    const detection = received as Detection;
    const { isNot } = this;

    if (typeof detection !== 'object' || detection === null) {
      return {
        pass: false,
        message: () => `Expected value to be an object, got ${typeof received}`,
      };
    }

    const errors: string[] = [];

    // Required fields
    if (!detection.id || typeof detection.id !== 'number' || detection.id <= 0) {
      errors.push('Detection must have a positive integer id');
    }

    if (!detection.camera_id || typeof detection.camera_id !== 'string') {
      errors.push("Detection must have a non-empty 'camera_id' string");
    }

    if (!detection.file_path || typeof detection.file_path !== 'string') {
      errors.push("Detection must have a non-empty 'file_path' string");
    }

    if (!detection.detected_at || !isValidISODate(detection.detected_at)) {
      errors.push('Detection must have a valid ISO 8601 detected_at timestamp');
    }

    // Optional fields validation
    if (detection.confidence !== null && detection.confidence !== undefined) {
      if (
        typeof detection.confidence !== 'number' ||
        detection.confidence < 0 ||
        detection.confidence > 1
      ) {
        errors.push('Detection confidence must be a number between 0 and 1 or null');
      }
    }

    // Bounding box - all or none
    const bboxFields = ['bbox_x', 'bbox_y', 'bbox_width', 'bbox_height'] as const;
    const bboxValues = bboxFields.map((field) => detection[field]);
    const hasSomeBbox = bboxValues.some((val) => val !== null && val !== undefined);
    const hasAllBbox = bboxValues.every((val) => val !== null && val !== undefined);

    if (hasSomeBbox && !hasAllBbox) {
      errors.push('If any bounding box field is set, all must be set (bbox_x, y, width, height)');
    }

    if (hasAllBbox) {
      bboxFields.forEach((field) => {
        const value = detection[field];
        if (typeof value !== 'number' || value < 0) {
          errors.push(`Detection ${field} must be a non-negative number`);
        }
      });
    }

    if (detection.media_type !== null && detection.media_type !== undefined) {
      const validTypes = ['image', 'video'];
      if (!validTypes.includes(detection.media_type)) {
        errors.push(`Detection media_type must be one of ${validTypes.join(', ')} or null`);
      }
    }

    if (detection.duration !== null && detection.duration !== undefined) {
      if (typeof detection.duration !== 'number' || detection.duration <= 0) {
        errors.push('Detection duration must be a positive number or null');
      }
    }

    const pass = errors.length === 0;

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected detection not to be valid, but it is valid`;
        }
        return `Expected detection to be valid, but found errors:\n${errors.join('\n')}`;
      },
    };
  },

  /**
   * Assert that the object has the expected risk level.
   */
  toHaveRiskLevel(received: unknown, expected: RiskLevel) {
    const obj = received as { risk_level?: string };
    const { isNot } = this;

    if (typeof obj !== 'object' || obj === null) {
      return {
        pass: false,
        message: () => `Expected value to be an object with risk_level property`,
      };
    }

    const pass = obj.risk_level === expected;

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected risk_level not to be ${expected}, but it is`;
        }
        return `Expected risk_level to be ${expected}, but got ${obj.risk_level}`;
      },
    };
  },

  /**
   * Assert that a numeric value is a valid risk score (0-100).
   */
  toBeValidRiskScore(received: unknown) {
    const { isNot } = this;

    if (typeof received !== 'number') {
      return {
        pass: false,
        message: () => `Expected value to be a number, got ${typeof received}`,
      };
    }

    const pass = received >= 0 && received <= 100;

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected value not to be a valid risk score, but it is`;
        }
        return `Expected risk score to be between 0 and 100, but got ${received}`;
      },
    };
  },

  /**
   * Assert that an HTML element is accessible.
   * Checks for basic ARIA attributes and semantic HTML.
   */
  toBeAccessible(received: unknown) {
    const { isNot } = this;

    if (!(received instanceof HTMLElement)) {
      return {
        pass: false,
        message: () => `Expected value to be an HTMLElement`,
      };
    }

    const element = received;
    const errors: string[] = [];

    // Check for interactive elements without accessible names
    const interactiveTags = ['button', 'a', 'input', 'select', 'textarea'];
    if (interactiveTags.includes(element.tagName.toLowerCase())) {
      const hasAccessibleName =
        element.hasAttribute('aria-label') ||
        element.hasAttribute('aria-labelledby') ||
        element.textContent?.trim() ||
        (element.tagName.toLowerCase() === 'input' &&
          (element.hasAttribute('placeholder') || element.hasAttribute('title')));

      if (!hasAccessibleName) {
        errors.push(`Interactive element <${element.tagName.toLowerCase()}> lacks accessible name`);
      }
    }

    // Check for images without alt text
    if (element.tagName.toLowerCase() === 'img' && !element.hasAttribute('alt')) {
      errors.push('Image element lacks alt attribute');
    }

    // Check for buttons with disabled state
    if (element.tagName.toLowerCase() === 'button' && element.hasAttribute('disabled')) {
      if (!element.hasAttribute('aria-disabled')) {
        errors.push('Disabled button should have aria-disabled attribute');
      }
    }

    const pass = errors.length === 0;

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected element not to be accessible, but it is`;
        }
        return `Expected element to be accessible, but found issues:\n${errors.join('\n')}`;
      },
    };
  },

  /**
   * Assert that a string is a valid ISO 8601 date.
   */
  toBeValidISODate(received: unknown) {
    const { isNot } = this;
    const pass = isValidISODate(received);

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected value not to be a valid ISO 8601 date, but it is`;
        }
        return `Expected value to be a valid ISO 8601 date`;
      },
    };
  },

  /**
   * Assert that an object is a valid paginated response.
   */
  toBeValidPaginatedResponse(received: unknown, collectionKey: string) {
    const data = received as Record<string, unknown>;
    const { isNot } = this;

    if (typeof data !== 'object' || data === null) {
      return {
        pass: false,
        message: () => `Expected value to be an object, got ${typeof received}`,
      };
    }

    const errors: string[] = [];

    // Check collection key
    if (!(collectionKey in data)) {
      errors.push(`Paginated response must have '${collectionKey}' field`);
    } else if (!Array.isArray(data[collectionKey])) {
      errors.push(`Paginated response '${collectionKey}' must be an array`);
    }

    // Check pagination metadata
    if (!('count' in data)) {
      errors.push("Paginated response must have 'count' field");
    } else if (typeof data.count !== 'number' || data.count < 0) {
      errors.push('Pagination count must be a non-negative number');
    }

    if (!('limit' in data)) {
      errors.push("Paginated response must have 'limit' field");
    } else if (typeof data.limit !== 'number' || data.limit <= 0) {
      errors.push('Pagination limit must be a positive number');
    }

    if (!('offset' in data)) {
      errors.push("Paginated response must have 'offset' field");
    } else if (typeof data.offset !== 'number' || data.offset < 0) {
      errors.push('Pagination offset must be a non-negative number');
    }

    const pass = errors.length === 0;

    return {
      pass,
      message: () => {
        if (isNot) {
          return `Expected not to be a valid paginated response, but it is`;
        }
        return `Expected to be a valid paginated response, but found errors:\n${errors.join('\n')}`;
      },
    };
  },
});
