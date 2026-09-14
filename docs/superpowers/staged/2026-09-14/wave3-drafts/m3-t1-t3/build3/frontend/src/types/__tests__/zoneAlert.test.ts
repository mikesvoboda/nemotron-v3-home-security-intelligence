/**
 * Tests for Zone Alert Types (NEM-3196)
 */

import { describe, expect, it } from 'vitest';

import {
  TrustViolationType,
  AlertPriority,
  TRUST_VIOLATION_TYPE_CONFIG,
  severityToPriority,
  isTrustViolationType,
  isTrustViolation,
  isUnifiedZoneAlert,
  isAnomalyAlert,
  isTrustViolationAlert,
} from '../zoneAlert';
import { AnomalyType, AnomalySeverity } from '../zoneAnomaly';

import type { TrustViolation, UnifiedZoneAlert } from '../zoneAlert';
import type { ZoneAnomaly } from '../zoneAnomaly';

describe('TrustViolationType enum', () => {
  it('has correct values', () => {
    expect(TrustViolationType.UNKNOWN_ENTITY).toBe('unknown_entity');
    expect(TrustViolationType.UNAUTHORIZED_TIME).toBe('unauthorized_time');
    expect(TrustViolationType.RESTRICTED_ZONE).toBe('restricted_zone');
  });
});

describe('AlertPriority enum', () => {
  it('has correct values with CRITICAL being highest priority (0)', () => {
    expect(AlertPriority.CRITICAL).toBe(0);
    expect(AlertPriority.WARNING).toBe(1);
    expect(AlertPriority.INFO).toBe(2);
  });

  it('maintains correct ordering for sorting', () => {
    const priorities = [AlertPriority.INFO, AlertPriority.CRITICAL, AlertPriority.WARNING];
    const sorted = priorities.sort((a, b) => a - b);
    expect(sorted).toEqual([AlertPriority.CRITICAL, AlertPriority.WARNING, AlertPriority.INFO]);
  });
});

describe('TRUST_VIOLATION_TYPE_CONFIG', () => {
  it('has configuration for all trust violation types', () => {
    expect(TRUST_VIOLATION_TYPE_CONFIG[TrustViolationType.UNKNOWN_ENTITY]).toBeDefined();
    expect(TRUST_VIOLATION_TYPE_CONFIG[TrustViolationType.UNAUTHORIZED_TIME]).toBeDefined();
    expect(TRUST_VIOLATION_TYPE_CONFIG[TrustViolationType.RESTRICTED_ZONE]).toBeDefined();
  });

  it('has required properties for each config', () => {
    Object.values(TrustViolationType).forEach((type) => {
      const config = TRUST_VIOLATION_TYPE_CONFIG[type];
      expect(config.label).toBeTruthy();
      expect(config.description).toBeTruthy();
      expect(config.icon).toBeTruthy();
    });
  });
});

describe('severityToPriority', () => {
  it('maps critical severity to CRITICAL priority', () => {
    expect(severityToPriority('critical')).toBe(AlertPriority.CRITICAL);
  });

  it('maps warning severity to WARNING priority', () => {
    expect(severityToPriority('warning')).toBe(AlertPriority.WARNING);
  });

  it('maps info severity to INFO priority', () => {
    expect(severityToPriority('info')).toBe(AlertPriority.INFO);
  });

  it('defaults to INFO for unknown severity', () => {
    expect(severityToPriority('unknown' as AnomalySeverity)).toBe(AlertPriority.INFO);
  });
});

describe('isTrustViolationType', () => {
  it('returns true for valid trust violation types', () => {
    expect(isTrustViolationType('unknown_entity')).toBe(true);
    expect(isTrustViolationType('unauthorized_time')).toBe(true);
    expect(isTrustViolationType('restricted_zone')).toBe(true);
  });

  it('returns false for invalid types', () => {
    expect(isTrustViolationType('invalid')).toBe(false);
    expect(isTrustViolationType('')).toBe(false);
    expect(isTrustViolationType(null)).toBe(false);
    expect(isTrustViolationType(undefined)).toBe(false);
    expect(isTrustViolationType(123)).toBe(false);
    expect(isTrustViolationType({})).toBe(false);
  });
});

describe('isTrustViolation', () => {
  const validViolation: TrustViolation = {
    id: 'violation-123',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    violation_type: TrustViolationType.UNKNOWN_ENTITY,
    severity: 'critical',
    title: 'Unknown person detected',
    description: 'An unknown person was detected in the restricted zone',
    entity_id: 'entity-123',
    entity_type: 'person',
    detection_id: 1,
    thumbnail_url: 'https://example.com/thumb.jpg',
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: '2024-01-15T10:00:00Z',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
  };

  it('returns true for valid trust violation objects', () => {
    expect(isTrustViolation(validViolation)).toBe(true);
  });

  it('returns true for minimal valid trust violation', () => {
    const minimal = {
      id: 'v-1',
      zone_id: 'z-1',
      camera_id: 'c-1',
      violation_type: 'unknown_entity',
      severity: 'warning',
      title: 'Test',
      acknowledged: false,
      timestamp: '2024-01-01T00:00:00Z',
    };
    expect(isTrustViolation(minimal)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isTrustViolation(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isTrustViolation(undefined)).toBe(false);
  });

  it('returns false for non-objects', () => {
    expect(isTrustViolation('string')).toBe(false);
    expect(isTrustViolation(123)).toBe(false);
    expect(isTrustViolation(true)).toBe(false);
  });

  it('returns false for missing required fields', () => {
    expect(isTrustViolation({ id: 'v-1' })).toBe(false);
    expect(isTrustViolation({ ...validViolation, id: undefined })).toBe(false);
    expect(isTrustViolation({ ...validViolation, zone_id: undefined })).toBe(false);
    expect(isTrustViolation({ ...validViolation, camera_id: undefined })).toBe(false);
    expect(isTrustViolation({ ...validViolation, violation_type: undefined })).toBe(false);
    expect(isTrustViolation({ ...validViolation, title: undefined })).toBe(false);
    expect(isTrustViolation({ ...validViolation, acknowledged: undefined })).toBe(false);
    expect(isTrustViolation({ ...validViolation, timestamp: undefined })).toBe(false);
  });

  it('returns false for invalid violation_type', () => {
    expect(isTrustViolation({ ...validViolation, violation_type: 'invalid' })).toBe(false);
  });
});

describe('isUnifiedZoneAlert', () => {
  const createMockAnomaly = (): ZoneAnomaly => ({
    id: 'anomaly-123',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.WARNING,
    title: 'Unusual activity time',
    description: 'Activity detected at unusual hour',
    expected_value: 10,
    actual_value: 50,
    deviation: 4.0,
    detection_id: 1,
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: '2024-01-15T03:00:00Z',
    created_at: '2024-01-15T03:00:00Z',
    updated_at: '2024-01-15T03:00:00Z',
  });

  const validUnifiedAlert: UnifiedZoneAlert = {
    id: 'alert-123',
    source: 'anomaly',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    severity: 'warning',
    priority: AlertPriority.WARNING,
    title: 'Test Alert',
    description: 'Test description',
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    timestamp: '2024-01-15T10:00:00Z',
    originalAlert: createMockAnomaly(),
  };

  it('returns true for valid unified alert', () => {
    expect(isUnifiedZoneAlert(validUnifiedAlert)).toBe(true);
  });

  it('returns true for trust_violation source', () => {
    const alert = { ...validUnifiedAlert, source: 'trust_violation' as const };
    expect(isUnifiedZoneAlert(alert)).toBe(true);
  });

  it('returns false for invalid source', () => {
    const alert = { ...validUnifiedAlert, source: 'invalid' };
    expect(isUnifiedZoneAlert(alert)).toBe(false);
  });

  it('returns false for null', () => {
    expect(isUnifiedZoneAlert(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isUnifiedZoneAlert(undefined)).toBe(false);
  });

  it('returns false for non-objects', () => {
    expect(isUnifiedZoneAlert('string')).toBe(false);
    expect(isUnifiedZoneAlert(123)).toBe(false);
  });

  it('returns false for missing required fields', () => {
    expect(isUnifiedZoneAlert({ id: 'a-1' })).toBe(false);
  });
});

describe('isAnomalyAlert', () => {
  const createMockAnomaly = (): ZoneAnomaly => ({
    id: 'anomaly-123',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.WARNING,
    title: 'Unusual activity time',
    description: 'Activity detected at unusual hour',
    expected_value: 10,
    actual_value: 50,
    deviation: 4.0,
    detection_id: 1,
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: '2024-01-15T03:00:00Z',
    created_at: '2024-01-15T03:00:00Z',
    updated_at: '2024-01-15T03:00:00Z',
  });

  it('returns true for anomaly source alerts', () => {
    const alert: UnifiedZoneAlert = {
      id: 'alert-123',
      source: 'anomaly',
      zone_id: 'zone-456',
      camera_id: 'cam-789',
      severity: 'warning',
      priority: AlertPriority.WARNING,
      title: 'Test',
      description: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      timestamp: '2024-01-15T10:00:00Z',
      originalAlert: createMockAnomaly(),
    };
    expect(isAnomalyAlert(alert)).toBe(true);
  });

  it('returns false for trust_violation source alerts', () => {
    const violation: TrustViolation = {
      id: 'v-1',
      zone_id: 'z-1',
      camera_id: 'c-1',
      violation_type: TrustViolationType.UNKNOWN_ENTITY,
      severity: 'critical',
      title: 'Test',
      description: null,
      entity_id: null,
      entity_type: null,
      detection_id: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      acknowledged_by: null,
      timestamp: '2024-01-15T10:00:00Z',
      created_at: '2024-01-15T10:00:00Z',
      updated_at: '2024-01-15T10:00:00Z',
    };
    const alert: UnifiedZoneAlert = {
      id: 'alert-456',
      source: 'trust_violation',
      zone_id: 'zone-456',
      camera_id: 'cam-789',
      severity: 'critical',
      priority: AlertPriority.CRITICAL,
      title: 'Test',
      description: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      timestamp: '2024-01-15T10:00:00Z',
      originalAlert: violation,
    };
    expect(isAnomalyAlert(alert)).toBe(false);
  });
});

describe('isTrustViolationAlert', () => {
  const createMockAnomaly = (): ZoneAnomaly => ({
    id: 'anomaly-123',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    anomaly_type: AnomalyType.UNUSUAL_TIME,
    severity: AnomalySeverity.WARNING,
    title: 'Unusual activity time',
    description: 'Activity detected at unusual hour',
    expected_value: 10,
    actual_value: 50,
    deviation: 4.0,
    detection_id: 1,
    thumbnail_url: null,
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: '2024-01-15T03:00:00Z',
    created_at: '2024-01-15T03:00:00Z',
    updated_at: '2024-01-15T03:00:00Z',
  });

  it('returns true for trust_violation source alerts', () => {
    const violation: TrustViolation = {
      id: 'v-1',
      zone_id: 'z-1',
      camera_id: 'c-1',
      violation_type: TrustViolationType.RESTRICTED_ZONE,
      severity: 'critical',
      title: 'Test',
      description: null,
      entity_id: null,
      entity_type: null,
      detection_id: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      acknowledged_by: null,
      timestamp: '2024-01-15T10:00:00Z',
      created_at: '2024-01-15T10:00:00Z',
      updated_at: '2024-01-15T10:00:00Z',
    };
    const alert: UnifiedZoneAlert = {
      id: 'alert-456',
      source: 'trust_violation',
      zone_id: 'zone-456',
      camera_id: 'cam-789',
      severity: 'critical',
      priority: AlertPriority.CRITICAL,
      title: 'Test',
      description: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      timestamp: '2024-01-15T10:00:00Z',
      originalAlert: violation,
    };
    expect(isTrustViolationAlert(alert)).toBe(true);
  });

  it('returns false for anomaly source alerts', () => {
    const alert: UnifiedZoneAlert = {
      id: 'alert-123',
      source: 'anomaly',
      zone_id: 'zone-456',
      camera_id: 'cam-789',
      severity: 'warning',
      priority: AlertPriority.WARNING,
      title: 'Test',
      description: null,
      thumbnail_url: null,
      acknowledged: false,
      acknowledged_at: null,
      timestamp: '2024-01-15T10:00:00Z',
      originalAlert: createMockAnomaly(),
    };
    expect(isTrustViolationAlert(alert)).toBe(false);
  });
});
