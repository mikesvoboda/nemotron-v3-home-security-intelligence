/**
 * Tests for custom assertion matchers.
 */

import { describe, it, expect } from 'vitest';

import {
  cameraFactory,
  eventFactory,
  detectionFactory,
} from './factories';
import {
  expectRiskLevel,
  expectValidCamera,
  expectValidEvent,
  expectValidDetection,
  expectValidBoundingBox,
  expectRecentTimestamp,
  expectPastTimestamp,
  expectTimestampBefore,
  expectSortedBy,
  expectUniqueBy,
  expectLoading,
  expectLoaded,
  expectError,
} from './matchers';

// ============================================================================
// Risk Level Tests
// ============================================================================

describe('expectRiskLevel', () => {
  it('validates low risk scores', () => {
    expect(() => expectRiskLevel(0).toBeLow()).not.toThrow();
    expect(() => expectRiskLevel(29).toBeLow()).not.toThrow();
  });

  it('validates medium risk scores', () => {
    expect(() => expectRiskLevel(30).toBeMedium()).not.toThrow();
    expect(() => expectRiskLevel(50).toBeMedium()).not.toThrow();
    expect(() => expectRiskLevel(69).toBeMedium()).not.toThrow();
  });

  it('validates high risk scores', () => {
    expect(() => expectRiskLevel(70).toBeHigh()).not.toThrow();
    expect(() => expectRiskLevel(100).toBeHigh()).not.toThrow();
  });

  it('validates any valid score', () => {
    expect(() => expectRiskLevel(0).toBeValid()).not.toThrow();
    expect(() => expectRiskLevel(50).toBeValid()).not.toThrow();
    expect(() => expectRiskLevel(100).toBeValid()).not.toThrow();
  });

  it('throws for invalid ranges', () => {
    expect(() => expectRiskLevel(30).toBeLow()).toThrow();
    expect(() => expectRiskLevel(69).toBeHigh()).toThrow();
    expect(() => expectRiskLevel(-1).toBeValid()).toThrow();
    expect(() => expectRiskLevel(101).toBeValid()).toThrow();
  });
});

// ============================================================================
// Data Structure Tests
// ============================================================================

describe('expectValidCamera', () => {
  it('validates camera structure', () => {
    const camera = cameraFactory();
    expect(() => expectValidCamera(camera)).not.toThrow();
  });

  it('throws for invalid camera', () => {
    const invalidCamera = { id: 'test' }; // Missing required fields
    expect(() => expectValidCamera(invalidCamera)).toThrow();
  });

  it('validates status enum', () => {
    const camera = cameraFactory({ status: 'online' });
    expect(() => expectValidCamera(camera)).not.toThrow();

    const invalidCamera = cameraFactory({ status: 'invalid' as any });
    expect(() => expectValidCamera(invalidCamera)).toThrow();
  });
});

describe('expectValidEvent', () => {
  it('validates event structure', () => {
    const event = eventFactory();
    expect(() => expectValidEvent(event)).not.toThrow();
  });

  it('throws for invalid event', () => {
    const invalidEvent = { id: 1 }; // Missing required fields
    expect(() => expectValidEvent(invalidEvent)).toThrow();
  });

  it('validates risk level enum', () => {
    const event = eventFactory({ risk_level: 'high' });
    expect(() => expectValidEvent(event)).not.toThrow();

    const invalidEvent = eventFactory({ risk_level: 'invalid' as any });
    expect(() => expectValidEvent(invalidEvent)).toThrow();
  });

  it('validates risk score range', () => {
    const event = eventFactory({ risk_score: 50 });
    expect(() => expectValidEvent(event)).not.toThrow();

    const invalidEvent = eventFactory({ risk_score: 150 });
    expect(() => expectValidEvent(invalidEvent)).toThrow();
  });
});

describe('expectValidDetection', () => {
  it('validates detection structure', () => {
    const detection = detectionFactory();
    expect(() => expectValidDetection(detection)).not.toThrow();
  });

  it('throws for invalid detection', () => {
    const invalidDetection = { id: 1 }; // Missing required fields
    expect(() => expectValidDetection(invalidDetection)).toThrow();
  });

  it('validates confidence range', () => {
    const detection = detectionFactory({ confidence: 0.85 });
    expect(() => expectValidDetection(detection)).not.toThrow();

    const invalidDetection = detectionFactory({ confidence: 1.5 });
    expect(() => expectValidDetection(invalidDetection)).toThrow();
  });
});

// ============================================================================
// Bounding Box Tests
// ============================================================================

describe('expectValidBoundingBox', () => {
  it('validates correct bbox', () => {
    expect(() => expectValidBoundingBox([100, 100, 200, 200])).not.toThrow();
  });

  it('throws for incorrect length', () => {
    expect(() => expectValidBoundingBox([100, 100])).toThrow();
  });

  it('throws for invalid coordinates', () => {
    // x2 <= x1
    expect(() => expectValidBoundingBox([200, 100, 100, 200])).toThrow();

    // y2 <= y1
    expect(() => expectValidBoundingBox([100, 200, 200, 100])).toThrow();

    // Negative coordinates
    expect(() => expectValidBoundingBox([-10, 100, 200, 200])).toThrow();
  });
});

// ============================================================================
// Timestamp Tests
// ============================================================================

describe('expectRecentTimestamp', () => {
  it('validates recent timestamp', () => {
    const now = new Date().toISOString();
    expect(() => expectRecentTimestamp(now, 60)).not.toThrow();
  });

  it('throws for old timestamp', () => {
    const old = new Date(Date.now() - 120000).toISOString(); // 2 minutes ago
    expect(() => expectRecentTimestamp(old, 60)).toThrow();
  });

  it('uses custom max age', () => {
    const recent = new Date(Date.now() - 90000).toISOString(); // 90 seconds ago
    expect(() => expectRecentTimestamp(recent, 120)).not.toThrow();
    expect(() => expectRecentTimestamp(recent, 60)).toThrow();
  });
});

describe('expectPastTimestamp', () => {
  it('validates past timestamp', () => {
    const past = new Date(Date.now() - 60000).toISOString();
    expect(() => expectPastTimestamp(past)).not.toThrow();
  });

  it('throws for future timestamp', () => {
    const future = new Date(Date.now() + 60000).toISOString();
    expect(() => expectPastTimestamp(future)).toThrow();
  });
});

describe('expectTimestampBefore', () => {
  it('validates timestamp ordering', () => {
    const ts1 = new Date(Date.now() - 120000).toISOString();
    const ts2 = new Date(Date.now() - 60000).toISOString();
    expect(() => expectTimestampBefore(ts1, ts2)).not.toThrow();
  });

  it('throws for incorrect ordering', () => {
    const ts1 = new Date(Date.now() - 60000).toISOString();
    const ts2 = new Date(Date.now() - 120000).toISOString();
    expect(() => expectTimestampBefore(ts1, ts2)).toThrow();
  });
});

// ============================================================================
// Array Tests
// ============================================================================

describe('expectSortedBy', () => {
  it('validates ascending sort', () => {
    const items = [
      { value: 1 },
      { value: 2 },
      { value: 3 },
    ];
    expect(() => expectSortedBy(items, 'value', 'asc')).not.toThrow();
  });

  it('validates descending sort', () => {
    const items = [
      { value: 3 },
      { value: 2 },
      { value: 1 },
    ];
    expect(() => expectSortedBy(items, 'value', 'desc')).not.toThrow();
  });

  it('throws for unsorted array', () => {
    const items = [
      { value: 1 },
      { value: 3 },
      { value: 2 },
    ];
    expect(() => expectSortedBy(items, 'value', 'asc')).toThrow();
  });

  it('handles equal values', () => {
    const items = [
      { value: 1 },
      { value: 1 },
      { value: 2 },
    ];
    expect(() => expectSortedBy(items, 'value', 'asc')).not.toThrow();
  });
});

describe('expectUniqueBy', () => {
  it('validates unique values', () => {
    const items = [
      { id: 1 },
      { id: 2 },
      { id: 3 },
    ];
    expect(() => expectUniqueBy(items, 'id')).not.toThrow();
  });

  it('throws for duplicate values', () => {
    const items = [
      { id: 1 },
      { id: 2 },
      { id: 1 },
    ];
    expect(() => expectUniqueBy(items, 'id')).toThrow();
  });
});

// ============================================================================
// Loading State Tests
// ============================================================================

describe('expectLoading', () => {
  it('validates loading state', () => {
    const result = { isLoading: true, data: undefined };
    expect(() => expectLoading(result)).not.toThrow();
  });

  it('throws for non-loading state', () => {
    const result = { isLoading: false, data: { test: 'data' } };
    expect(() => expectLoading(result)).toThrow();
  });
});

describe('expectLoaded', () => {
  it('validates loaded state', () => {
    const result = { isLoading: false, data: { test: 'data' } };
    expect(() => expectLoaded(result)).not.toThrow();
  });

  it('throws for loading state', () => {
    const result = { isLoading: true, data: undefined };
    expect(() => expectLoaded(result)).toThrow();
  });

  it('throws when data is undefined', () => {
    const result = { isLoading: false, data: undefined };
    expect(() => expectLoaded(result)).toThrow();
  });
});

describe('expectError', () => {
  it('validates error state', () => {
    const result = {
      isLoading: false,
      error: new Error('Test error'),
    };
    expect(() => expectError(result)).not.toThrow();
  });

  it('validates error message', () => {
    const result = {
      isLoading: false,
      error: new Error('Failed to fetch'),
    };
    expect(() => expectError(result, 'Failed to fetch')).not.toThrow();
  });

  it('throws for non-error state', () => {
    const result = {
      isLoading: false,
      error: null,
    };
    expect(() => expectError(result)).toThrow();
  });

  it('throws for wrong error message', () => {
    const result = {
      isLoading: false,
      error: new Error('Wrong message'),
    };
    expect(() => expectError(result, 'Expected message')).toThrow();
  });
});
