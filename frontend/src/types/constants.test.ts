/**
 * Tests for type-safe constants with const assertions.
 *
 * These tests verify:
 * - Const objects are frozen and immutable
 * - Type guards correctly validate values
 * - Value arrays contain all expected values
 * - Runtime behavior matches compile-time types
 */
import { describe, it, expect } from 'vitest';

import {
  // Risk Levels
  RISK_LEVELS,
  RISK_LEVEL_VALUES,
  isRiskLevel,
  type RiskLevel,
  // Connection States
  CONNECTION_STATES,
  CONNECTION_STATE_VALUES,
  isConnectionState,
  type ConnectionState,
  // Service Statuses
  SERVICE_STATUSES,
  SERVICE_STATUS_VALUES,
  isServiceStatus,
  type ServiceStatus,
  // Health Statuses
  HEALTH_STATUSES,
  HEALTH_STATUS_VALUES,
  isHealthStatus,
  type HealthStatus,
} from './constants';

// ============================================================================
// Risk Level Tests
// ============================================================================

describe('RISK_LEVELS', () => {
  describe('const object', () => {
    it('has all expected values', () => {
      expect(RISK_LEVELS.LOW).toBe('low');
      expect(RISK_LEVELS.MEDIUM).toBe('medium');
      expect(RISK_LEVELS.HIGH).toBe('high');
      expect(RISK_LEVELS.CRITICAL).toBe('critical');
    });

    it('is frozen and immutable', () => {
      expect(Object.isFrozen(RISK_LEVELS)).toBe(true);

      // Attempting to modify should fail silently in non-strict mode
      // or throw in strict mode - either way the value should not change
      const originalValue = RISK_LEVELS.LOW;
      expect(() => {
        // @ts-expect-error - Testing runtime immutability
        RISK_LEVELS.LOW = 'modified';
      }).toThrow();
      expect(RISK_LEVELS.LOW).toBe(originalValue);
    });

    it('has exactly 4 values', () => {
      expect(Object.keys(RISK_LEVELS)).toHaveLength(4);
    });
  });

  describe('RISK_LEVEL_VALUES array', () => {
    it('contains all risk level values', () => {
      expect(RISK_LEVEL_VALUES).toContain('low');
      expect(RISK_LEVEL_VALUES).toContain('medium');
      expect(RISK_LEVEL_VALUES).toContain('high');
      expect(RISK_LEVEL_VALUES).toContain('critical');
    });

    it('has correct length', () => {
      expect(RISK_LEVEL_VALUES).toHaveLength(4);
    });

    it('is frozen', () => {
      expect(Object.isFrozen(RISK_LEVEL_VALUES)).toBe(true);
    });
  });

  describe('isRiskLevel type guard', () => {
    it('returns true for valid risk levels', () => {
      expect(isRiskLevel('low')).toBe(true);
      expect(isRiskLevel('medium')).toBe(true);
      expect(isRiskLevel('high')).toBe(true);
      expect(isRiskLevel('critical')).toBe(true);
    });

    it('returns false for invalid strings', () => {
      expect(isRiskLevel('invalid')).toBe(false);
      expect(isRiskLevel('HIGH')).toBe(false); // Case-sensitive
      expect(isRiskLevel('Low')).toBe(false);
      expect(isRiskLevel('')).toBe(false);
    });

    it('returns false for non-string values', () => {
      expect(isRiskLevel(null)).toBe(false);
      expect(isRiskLevel(undefined)).toBe(false);
      expect(isRiskLevel(123)).toBe(false);
      expect(isRiskLevel({})).toBe(false);
      expect(isRiskLevel([])).toBe(false);
      expect(isRiskLevel(true)).toBe(false);
    });

    it('narrows type correctly', () => {
      const value: unknown = 'high';
      if (isRiskLevel(value)) {
        // TypeScript should narrow to RiskLevel
        const level: RiskLevel = value;
        expect(level).toBe('high');
      }
    });
  });
});

// ============================================================================
// Connection State Tests
// ============================================================================

describe('CONNECTION_STATES', () => {
  describe('const object', () => {
    it('has all expected values', () => {
      expect(CONNECTION_STATES.CONNECTED).toBe('connected');
      expect(CONNECTION_STATES.DISCONNECTED).toBe('disconnected');
      expect(CONNECTION_STATES.RECONNECTING).toBe('reconnecting');
      expect(CONNECTION_STATES.FAILED).toBe('failed');
    });

    it('is frozen and immutable', () => {
      expect(Object.isFrozen(CONNECTION_STATES)).toBe(true);

      const originalValue = CONNECTION_STATES.CONNECTED;
      expect(() => {
        // @ts-expect-error - Testing runtime immutability
        CONNECTION_STATES.CONNECTED = 'modified';
      }).toThrow();
      expect(CONNECTION_STATES.CONNECTED).toBe(originalValue);
    });

    it('has exactly 4 values', () => {
      expect(Object.keys(CONNECTION_STATES)).toHaveLength(4);
    });
  });

  describe('CONNECTION_STATE_VALUES array', () => {
    it('contains all connection state values', () => {
      expect(CONNECTION_STATE_VALUES).toContain('connected');
      expect(CONNECTION_STATE_VALUES).toContain('disconnected');
      expect(CONNECTION_STATE_VALUES).toContain('reconnecting');
      expect(CONNECTION_STATE_VALUES).toContain('failed');
    });

    it('has correct length', () => {
      expect(CONNECTION_STATE_VALUES).toHaveLength(4);
    });

    it('is frozen', () => {
      expect(Object.isFrozen(CONNECTION_STATE_VALUES)).toBe(true);
    });
  });

  describe('isConnectionState type guard', () => {
    it('returns true for valid connection states', () => {
      expect(isConnectionState('connected')).toBe(true);
      expect(isConnectionState('disconnected')).toBe(true);
      expect(isConnectionState('reconnecting')).toBe(true);
      expect(isConnectionState('failed')).toBe(true);
    });

    it('returns false for invalid strings', () => {
      expect(isConnectionState('invalid')).toBe(false);
      expect(isConnectionState('CONNECTED')).toBe(false);
      expect(isConnectionState('connecting')).toBe(false);
      expect(isConnectionState('')).toBe(false);
    });

    it('returns false for non-string values', () => {
      expect(isConnectionState(null)).toBe(false);
      expect(isConnectionState(undefined)).toBe(false);
      expect(isConnectionState(0)).toBe(false);
      expect(isConnectionState({})).toBe(false);
    });

    it('narrows type correctly', () => {
      const value: unknown = 'connected';
      if (isConnectionState(value)) {
        const state: ConnectionState = value;
        expect(state).toBe('connected');
      }
    });
  });
});

// ============================================================================
// Service Status Tests
// ============================================================================

describe('SERVICE_STATUSES', () => {
  describe('const object', () => {
    it('has all expected values', () => {
      expect(SERVICE_STATUSES.HEALTHY).toBe('healthy');
      expect(SERVICE_STATUSES.UNHEALTHY).toBe('unhealthy');
      expect(SERVICE_STATUSES.RESTARTING).toBe('restarting');
      expect(SERVICE_STATUSES.RESTART_FAILED).toBe('restart_failed');
      expect(SERVICE_STATUSES.FAILED).toBe('failed');
    });

    it('is frozen and immutable', () => {
      expect(Object.isFrozen(SERVICE_STATUSES)).toBe(true);

      const originalValue = SERVICE_STATUSES.HEALTHY;
      expect(() => {
        // @ts-expect-error - Testing runtime immutability
        SERVICE_STATUSES.HEALTHY = 'modified';
      }).toThrow();
      expect(SERVICE_STATUSES.HEALTHY).toBe(originalValue);
    });

    it('has exactly 5 values', () => {
      expect(Object.keys(SERVICE_STATUSES)).toHaveLength(5);
    });
  });

  describe('SERVICE_STATUS_VALUES array', () => {
    it('contains all service status values', () => {
      expect(SERVICE_STATUS_VALUES).toContain('healthy');
      expect(SERVICE_STATUS_VALUES).toContain('unhealthy');
      expect(SERVICE_STATUS_VALUES).toContain('restarting');
      expect(SERVICE_STATUS_VALUES).toContain('restart_failed');
      expect(SERVICE_STATUS_VALUES).toContain('failed');
    });

    it('has correct length', () => {
      expect(SERVICE_STATUS_VALUES).toHaveLength(5);
    });

    it('is frozen', () => {
      expect(Object.isFrozen(SERVICE_STATUS_VALUES)).toBe(true);
    });
  });

  describe('isServiceStatus type guard', () => {
    it('returns true for valid service statuses', () => {
      expect(isServiceStatus('healthy')).toBe(true);
      expect(isServiceStatus('unhealthy')).toBe(true);
      expect(isServiceStatus('restarting')).toBe(true);
      expect(isServiceStatus('restart_failed')).toBe(true);
      expect(isServiceStatus('failed')).toBe(true);
    });

    it('returns false for invalid strings', () => {
      expect(isServiceStatus('invalid')).toBe(false);
      expect(isServiceStatus('HEALTHY')).toBe(false);
      expect(isServiceStatus('restart-failed')).toBe(false);
      expect(isServiceStatus('')).toBe(false);
    });

    it('returns false for non-string values', () => {
      expect(isServiceStatus(null)).toBe(false);
      expect(isServiceStatus(undefined)).toBe(false);
      expect(isServiceStatus(1)).toBe(false);
      expect(isServiceStatus({})).toBe(false);
    });

    it('narrows type correctly', () => {
      const value: unknown = 'restarting';
      if (isServiceStatus(value)) {
        const status: ServiceStatus = value;
        expect(status).toBe('restarting');
      }
    });
  });
});

// ============================================================================
// Health Status Tests
// ============================================================================

describe('HEALTH_STATUSES', () => {
  describe('const object', () => {
    it('has all expected values', () => {
      expect(HEALTH_STATUSES.HEALTHY).toBe('healthy');
      expect(HEALTH_STATUSES.DEGRADED).toBe('degraded');
      expect(HEALTH_STATUSES.UNHEALTHY).toBe('unhealthy');
    });

    it('is frozen and immutable', () => {
      expect(Object.isFrozen(HEALTH_STATUSES)).toBe(true);

      const originalValue = HEALTH_STATUSES.HEALTHY;
      expect(() => {
        // @ts-expect-error - Testing runtime immutability
        HEALTH_STATUSES.HEALTHY = 'modified';
      }).toThrow();
      expect(HEALTH_STATUSES.HEALTHY).toBe(originalValue);
    });

    it('has exactly 3 values', () => {
      expect(Object.keys(HEALTH_STATUSES)).toHaveLength(3);
    });
  });

  describe('HEALTH_STATUS_VALUES array', () => {
    it('contains all health status values', () => {
      expect(HEALTH_STATUS_VALUES).toContain('healthy');
      expect(HEALTH_STATUS_VALUES).toContain('degraded');
      expect(HEALTH_STATUS_VALUES).toContain('unhealthy');
    });

    it('has correct length', () => {
      expect(HEALTH_STATUS_VALUES).toHaveLength(3);
    });

    it('is frozen', () => {
      expect(Object.isFrozen(HEALTH_STATUS_VALUES)).toBe(true);
    });
  });

  describe('isHealthStatus type guard', () => {
    it('returns true for valid health statuses', () => {
      expect(isHealthStatus('healthy')).toBe(true);
      expect(isHealthStatus('degraded')).toBe(true);
      expect(isHealthStatus('unhealthy')).toBe(true);
    });

    it('returns false for invalid strings', () => {
      expect(isHealthStatus('invalid')).toBe(false);
      expect(isHealthStatus('HEALTHY')).toBe(false);
      expect(isHealthStatus('ok')).toBe(false);
      expect(isHealthStatus('')).toBe(false);
    });

    it('returns false for non-string values', () => {
      expect(isHealthStatus(null)).toBe(false);
      expect(isHealthStatus(undefined)).toBe(false);
      expect(isHealthStatus(true)).toBe(false);
      expect(isHealthStatus({})).toBe(false);
    });

    it('narrows type correctly', () => {
      const value: unknown = 'degraded';
      if (isHealthStatus(value)) {
        const health: HealthStatus = value;
        expect(health).toBe('degraded');
      }
    });
  });
});

// ============================================================================
// Type Compatibility Tests
// ============================================================================

describe('Type Compatibility', () => {
  it('RiskLevel values can be used as RISK_LEVELS keys', () => {
    const level: RiskLevel = 'high';
    // This verifies the type is compatible for lookups
    const keys = Object.keys(RISK_LEVELS) as (keyof typeof RISK_LEVELS)[];
    const matchingKey = keys.find((k) => RISK_LEVELS[k] === level);
    expect(matchingKey).toBe('HIGH');
  });

  it('ConnectionState values can be used as CONNECTION_STATES keys', () => {
    const state: ConnectionState = 'reconnecting';
    const keys = Object.keys(
      CONNECTION_STATES
    ) as (keyof typeof CONNECTION_STATES)[];
    const matchingKey = keys.find((k) => CONNECTION_STATES[k] === state);
    expect(matchingKey).toBe('RECONNECTING');
  });

  it('ServiceStatus values can be used as SERVICE_STATUSES keys', () => {
    const status: ServiceStatus = 'restart_failed';
    const keys = Object.keys(
      SERVICE_STATUSES
    ) as (keyof typeof SERVICE_STATUSES)[];
    const matchingKey = keys.find((k) => SERVICE_STATUSES[k] === status);
    expect(matchingKey).toBe('RESTART_FAILED');
  });

  it('HealthStatus values can be used as HEALTH_STATUSES keys', () => {
    const health: HealthStatus = 'degraded';
    const keys = Object.keys(
      HEALTH_STATUSES
    ) as (keyof typeof HEALTH_STATUSES)[];
    const matchingKey = keys.find((k) => HEALTH_STATUSES[k] === health);
    expect(matchingKey).toBe('DEGRADED');
  });
});

// ============================================================================
// Exhaustiveness Check Tests
// ============================================================================

describe('Exhaustiveness Checks', () => {
  it('switch on RiskLevel can be exhaustive', () => {
    function getRiskColor(level: RiskLevel): string {
      switch (level) {
        case 'low':
          return 'green';
        case 'medium':
          return 'yellow';
        case 'high':
          return 'orange';
        case 'critical':
          return 'red';
        default: {
          // This should never be reached
          const _exhaustiveCheck: never = level;
          return _exhaustiveCheck;
        }
      }
    }

    expect(getRiskColor('low')).toBe('green');
    expect(getRiskColor('medium')).toBe('yellow');
    expect(getRiskColor('high')).toBe('orange');
    expect(getRiskColor('critical')).toBe('red');
  });

  it('switch on ConnectionState can be exhaustive', () => {
    function getConnectionIcon(state: ConnectionState): string {
      switch (state) {
        case 'connected':
          return 'check';
        case 'disconnected':
          return 'x';
        case 'reconnecting':
          return 'spinner';
        case 'failed':
          return 'alert';
        default: {
          const _exhaustiveCheck: never = state;
          return _exhaustiveCheck;
        }
      }
    }

    expect(getConnectionIcon('connected')).toBe('check');
    expect(getConnectionIcon('disconnected')).toBe('x');
    expect(getConnectionIcon('reconnecting')).toBe('spinner');
    expect(getConnectionIcon('failed')).toBe('alert');
  });

  it('switch on ServiceStatus can be exhaustive', () => {
    function getServiceBadgeVariant(status: ServiceStatus): string {
      switch (status) {
        case 'healthy':
          return 'success';
        case 'unhealthy':
          return 'danger';
        case 'restarting':
          return 'warning';
        case 'restart_failed':
          return 'danger';
        case 'failed':
          return 'danger';
        default: {
          const _exhaustiveCheck: never = status;
          return _exhaustiveCheck;
        }
      }
    }

    expect(getServiceBadgeVariant('healthy')).toBe('success');
    expect(getServiceBadgeVariant('unhealthy')).toBe('danger');
    expect(getServiceBadgeVariant('restarting')).toBe('warning');
    expect(getServiceBadgeVariant('restart_failed')).toBe('danger');
    expect(getServiceBadgeVariant('failed')).toBe('danger');
  });

  it('switch on HealthStatus can be exhaustive', () => {
    function getHealthDescription(health: HealthStatus): string {
      switch (health) {
        case 'healthy':
          return 'All systems operational';
        case 'degraded':
          return 'Some systems degraded';
        case 'unhealthy':
          return 'System experiencing issues';
        default: {
          const _exhaustiveCheck: never = health;
          return _exhaustiveCheck;
        }
      }
    }

    expect(getHealthDescription('healthy')).toBe('All systems operational');
    expect(getHealthDescription('degraded')).toBe('Some systems degraded');
    expect(getHealthDescription('unhealthy')).toBe(
      'System experiencing issues'
    );
  });
});
