/**
 * Tests for Type-Safe Constants
 */

import { describe, it, expect } from 'vitest';

import {
  RISK_LEVELS,
  RISK_LEVEL_CONFIG,
  HEALTH_STATUSES,
  HEALTH_STATUS_CONFIG,
  CONTAINER_STATUSES,
  CONTAINER_STATUS_CONFIG,
  OBJECT_TYPES,
  OBJECT_TYPE_CONFIG,
  CONFIDENCE_LEVELS,
  CONFIDENCE_THRESHOLDS,
  WS_MESSAGE_TYPES,
  DAYS_OF_WEEK,
  DAY_OF_WEEK_LABELS,
  DAY_OF_WEEK_SHORT,
  ALERT_SEVERITIES,
  ALERT_SEVERITY_CONFIG,
  MODEL_STATUSES,
  MODEL_STATUS_CONFIG,
  TIME_RANGES,
  TIME_RANGE_CONFIG,
  isRiskLevel,
  isHealthStatus,
  isContainerStatus,
  isObjectType,
  isModelStatus,
  isDayOfWeek,
  getRiskLevelFromScore,
  getConfidenceLevelFromScore,
  assertNever,
  type RiskLevel,
  type HealthStatus,
  type ContainerStatus,
  type ObjectType,
  type ModelStatus,
  type DayOfWeek,
} from './constants';

// ============================================================================
// Risk Level Tests
// ============================================================================

describe('Risk Level Constants', () => {
  it('has all expected risk levels', () => {
    expect(RISK_LEVELS).toEqual(['low', 'medium', 'high', 'critical']);
  });

  it('has config for all risk levels', () => {
    RISK_LEVELS.forEach((level) => {
      expect(RISK_LEVEL_CONFIG[level]).toBeDefined();
      expect(RISK_LEVEL_CONFIG[level].label).toBeDefined();
      expect(RISK_LEVEL_CONFIG[level].color).toBeDefined();
    });
  });

  it('has contiguous score ranges', () => {
    expect(RISK_LEVEL_CONFIG.low.minScore).toBe(0);
    expect(RISK_LEVEL_CONFIG.low.maxScore).toBe(29);
    expect(RISK_LEVEL_CONFIG.medium.minScore).toBe(30);
    expect(RISK_LEVEL_CONFIG.medium.maxScore).toBe(59);
    expect(RISK_LEVEL_CONFIG.high.minScore).toBe(60);
    expect(RISK_LEVEL_CONFIG.high.maxScore).toBe(84);
    expect(RISK_LEVEL_CONFIG.critical.minScore).toBe(85);
    expect(RISK_LEVEL_CONFIG.critical.maxScore).toBe(100);
  });

  describe('isRiskLevel', () => {
    it('returns true for valid risk levels', () => {
      expect(isRiskLevel('low')).toBe(true);
      expect(isRiskLevel('medium')).toBe(true);
      expect(isRiskLevel('high')).toBe(true);
      expect(isRiskLevel('critical')).toBe(true);
    });

    it('returns false for invalid values', () => {
      expect(isRiskLevel('invalid')).toBe(false);
      expect(isRiskLevel('')).toBe(false);
      expect(isRiskLevel(null)).toBe(false);
      expect(isRiskLevel(undefined)).toBe(false);
      expect(isRiskLevel(123)).toBe(false);
    });
  });

  describe('getRiskLevelFromScore', () => {
    it('returns correct risk level for boundary scores', () => {
      expect(getRiskLevelFromScore(0)).toBe('low');
      expect(getRiskLevelFromScore(29)).toBe('low');
      expect(getRiskLevelFromScore(30)).toBe('medium');
      expect(getRiskLevelFromScore(59)).toBe('medium');
      expect(getRiskLevelFromScore(60)).toBe('high');
      expect(getRiskLevelFromScore(84)).toBe('high');
      expect(getRiskLevelFromScore(85)).toBe('critical');
      expect(getRiskLevelFromScore(100)).toBe('critical');
    });

    it('returns correct risk level for mid-range scores', () => {
      expect(getRiskLevelFromScore(15)).toBe('low');
      expect(getRiskLevelFromScore(45)).toBe('medium');
      expect(getRiskLevelFromScore(72)).toBe('high');
      expect(getRiskLevelFromScore(95)).toBe('critical');
    });
  });
});

// ============================================================================
// Health Status Tests
// ============================================================================

describe('Health Status Constants', () => {
  it('has all expected health statuses', () => {
    expect(HEALTH_STATUSES).toEqual(['healthy', 'degraded', 'unhealthy']);
  });

  it('has config for all health statuses', () => {
    HEALTH_STATUSES.forEach((status) => {
      expect(HEALTH_STATUS_CONFIG[status]).toBeDefined();
      expect(HEALTH_STATUS_CONFIG[status].label).toBeDefined();
      expect(HEALTH_STATUS_CONFIG[status].icon).toBeDefined();
    });
  });

  describe('isHealthStatus', () => {
    it('returns true for valid health statuses', () => {
      expect(isHealthStatus('healthy')).toBe(true);
      expect(isHealthStatus('degraded')).toBe(true);
      expect(isHealthStatus('unhealthy')).toBe(true);
    });

    it('returns false for invalid values', () => {
      expect(isHealthStatus('unknown')).toBe(false);
      expect(isHealthStatus('')).toBe(false);
      expect(isHealthStatus(null)).toBe(false);
    });
  });
});

// ============================================================================
// Container Status Tests
// ============================================================================

describe('Container Status Constants', () => {
  it('has all expected container statuses', () => {
    expect(CONTAINER_STATUSES).toEqual([
      'running',
      'starting',
      'unhealthy',
      'stopped',
      'error',
      'unknown',
    ]);
  });

  it('has config for all container statuses', () => {
    CONTAINER_STATUSES.forEach((status) => {
      expect(CONTAINER_STATUS_CONFIG[status]).toBeDefined();
      expect(CONTAINER_STATUS_CONFIG[status].label).toBeDefined();
      expect(CONTAINER_STATUS_CONFIG[status].tailwindDot).toBeDefined();
    });
  });

  describe('isContainerStatus', () => {
    it('returns true for valid container statuses', () => {
      expect(isContainerStatus('running')).toBe(true);
      expect(isContainerStatus('starting')).toBe(true);
      expect(isContainerStatus('error')).toBe(true);
    });

    it('returns false for invalid values', () => {
      expect(isContainerStatus('pending')).toBe(false);
      expect(isContainerStatus('')).toBe(false);
    });
  });
});

// ============================================================================
// Object Type Tests
// ============================================================================

describe('Object Type Constants', () => {
  it('has all expected object types', () => {
    expect(OBJECT_TYPES).toEqual(['person', 'vehicle', 'animal', 'package']);
  });

  it('has config for all object types', () => {
    OBJECT_TYPES.forEach((type) => {
      expect(OBJECT_TYPE_CONFIG[type]).toBeDefined();
      expect(OBJECT_TYPE_CONFIG[type].label).toBeDefined();
      expect(OBJECT_TYPE_CONFIG[type].icon).toBeDefined();
    });
  });

  describe('isObjectType', () => {
    it('returns true for valid object types', () => {
      expect(isObjectType('person')).toBe(true);
      expect(isObjectType('vehicle')).toBe(true);
      expect(isObjectType('animal')).toBe(true);
      expect(isObjectType('package')).toBe(true);
    });

    it('returns false for invalid values', () => {
      expect(isObjectType('car')).toBe(false); // specific, not a category
      expect(isObjectType('dog')).toBe(false); // specific, not a category
    });
  });
});

// ============================================================================
// Confidence Level Tests
// ============================================================================

describe('Confidence Level Constants', () => {
  it('has all expected confidence levels', () => {
    expect(CONFIDENCE_LEVELS).toEqual(['low', 'medium', 'high']);
  });

  it('has contiguous thresholds', () => {
    expect(CONFIDENCE_THRESHOLDS.low.min).toBe(0);
    expect(CONFIDENCE_THRESHOLDS.low.max).toBe(0.5);
    expect(CONFIDENCE_THRESHOLDS.medium.min).toBe(0.5);
    expect(CONFIDENCE_THRESHOLDS.medium.max).toBe(0.8);
    expect(CONFIDENCE_THRESHOLDS.high.min).toBe(0.8);
    expect(CONFIDENCE_THRESHOLDS.high.max).toBe(1.0);
  });

  describe('getConfidenceLevelFromScore', () => {
    it('returns correct confidence level for boundary scores', () => {
      expect(getConfidenceLevelFromScore(0)).toBe('low');
      expect(getConfidenceLevelFromScore(0.49)).toBe('low');
      expect(getConfidenceLevelFromScore(0.5)).toBe('medium');
      expect(getConfidenceLevelFromScore(0.79)).toBe('medium');
      expect(getConfidenceLevelFromScore(0.8)).toBe('high');
      expect(getConfidenceLevelFromScore(1.0)).toBe('high');
    });
  });
});

// ============================================================================
// WebSocket Message Type Tests
// ============================================================================

describe('WebSocket Message Type Constants', () => {
  it('has all expected message types', () => {
    expect(WS_MESSAGE_TYPES).toEqual([
      'event',
      'system_status',
      'service_status',
      'ping',
      'pong',
      'error',
    ]);
  });
});

// ============================================================================
// Day of Week Tests
// ============================================================================

describe('Day of Week Constants', () => {
  it('has all 7 days', () => {
    expect(DAYS_OF_WEEK).toHaveLength(7);
    expect(DAYS_OF_WEEK[0]).toBe('monday');
    expect(DAYS_OF_WEEK[6]).toBe('sunday');
  });

  it('has labels for all days', () => {
    DAYS_OF_WEEK.forEach((day) => {
      expect(DAY_OF_WEEK_LABELS[day]).toBeDefined();
      expect(DAY_OF_WEEK_SHORT[day]).toBeDefined();
      expect(DAY_OF_WEEK_SHORT[day]).toHaveLength(3);
    });
  });

  describe('isDayOfWeek', () => {
    it('returns true for valid days', () => {
      expect(isDayOfWeek('monday')).toBe(true);
      expect(isDayOfWeek('friday')).toBe(true);
      expect(isDayOfWeek('sunday')).toBe(true);
    });

    it('returns false for invalid values', () => {
      expect(isDayOfWeek('Monday')).toBe(false); // case sensitive
      expect(isDayOfWeek('mon')).toBe(false);
      expect(isDayOfWeek('')).toBe(false);
    });
  });
});

// ============================================================================
// Alert Severity Tests
// ============================================================================

describe('Alert Severity Constants', () => {
  it('has all expected severities', () => {
    expect(ALERT_SEVERITIES).toEqual(['info', 'warning', 'critical']);
  });

  it('has config for all severities', () => {
    ALERT_SEVERITIES.forEach((severity) => {
      expect(ALERT_SEVERITY_CONFIG[severity]).toBeDefined();
      expect(ALERT_SEVERITY_CONFIG[severity].label).toBeDefined();
      expect(ALERT_SEVERITY_CONFIG[severity].icon).toBeDefined();
    });
  });
});

// ============================================================================
// Model Status Tests
// ============================================================================

describe('Model Status Constants', () => {
  it('has all expected model statuses', () => {
    expect(MODEL_STATUSES).toEqual(['loaded', 'unloaded', 'loading', 'error', 'disabled']);
  });

  it('has config for all model statuses', () => {
    MODEL_STATUSES.forEach((status) => {
      expect(MODEL_STATUS_CONFIG[status]).toBeDefined();
      expect(MODEL_STATUS_CONFIG[status].label).toBeDefined();
      expect(MODEL_STATUS_CONFIG[status].tailwindDot).toBeDefined();
    });
  });

  describe('isModelStatus', () => {
    it('returns true for valid model statuses', () => {
      expect(isModelStatus('loaded')).toBe(true);
      expect(isModelStatus('loading')).toBe(true);
      expect(isModelStatus('error')).toBe(true);
    });

    it('returns false for invalid values', () => {
      expect(isModelStatus('ready')).toBe(false);
      expect(isModelStatus('')).toBe(false);
    });
  });
});

// ============================================================================
// Time Range Tests
// ============================================================================

describe('Time Range Constants', () => {
  it('has all expected time ranges', () => {
    expect(TIME_RANGES).toEqual(['5m', '15m', '60m', '24h', '7d']);
  });

  it('has config with correct durations', () => {
    expect(TIME_RANGE_CONFIG['5m'].durationMs).toBe(5 * 60 * 1000);
    expect(TIME_RANGE_CONFIG['15m'].durationMs).toBe(15 * 60 * 1000);
    expect(TIME_RANGE_CONFIG['60m'].durationMs).toBe(60 * 60 * 1000);
    expect(TIME_RANGE_CONFIG['24h'].durationMs).toBe(24 * 60 * 60 * 1000);
    expect(TIME_RANGE_CONFIG['7d'].durationMs).toBe(7 * 24 * 60 * 60 * 1000);
  });
});

// ============================================================================
// assertNever Tests
// ============================================================================

describe('assertNever', () => {
  it('throws an error with default message', () => {
    // We can't actually pass a never type at runtime, so we cast
    expect(() => assertNever('unexpected' as never)).toThrow('Unexpected value: unexpected');
  });

  it('throws an error with custom message', () => {
    expect(() => assertNever('value' as never, 'Custom error message')).toThrow(
      'Custom error message'
    );
  });
});

// ============================================================================
// Type Inference Tests (Compile-time Verification)
// ============================================================================

describe('Type Inference', () => {
  it('correctly types risk level from array', () => {
    // TypeScript should infer the type correctly
    const level: RiskLevel = RISK_LEVELS[0];
    expect(level).toBe('low');
  });

  it('allows using literal types directly', () => {
    const health: HealthStatus = 'healthy';
    const container: ContainerStatus = 'running';
    const object: ObjectType = 'person';
    const model: ModelStatus = 'loaded';
    const day: DayOfWeek = 'monday';

    expect(health).toBe('healthy');
    expect(container).toBe('running');
    expect(object).toBe('person');
    expect(model).toBe('loaded');
    expect(day).toBe('monday');
  });

  it('exhaustiveness checking works in switch', () => {
    function getRiskLabel(level: RiskLevel): string {
      switch (level) {
        case 'low':
          return 'Safe';
        case 'medium':
          return 'Caution';
        case 'high':
          return 'Warning';
        case 'critical':
          return 'Danger';
        // No default needed - TypeScript verifies all cases
      }
    }

    expect(getRiskLabel('low')).toBe('Safe');
    expect(getRiskLabel('critical')).toBe('Danger');
  });
});
