/**
 * Tests for zone anomaly types (NEM-3199)
 *
 * Tests type guards and configuration constants.
 */
import { describe, it, expect } from 'vitest';

import {
  AnomalySeverity,
  AnomalyType,
  ANOMALY_SEVERITY_CONFIG,
  ANOMALY_TYPE_CONFIG,
  isAnomalySeverity,
  isAnomalyType,
  isZoneAnomaly,
  isZoneAnomalyEventPayload,
} from './zoneAnomaly';

describe('AnomalySeverity enum', () => {
  it('has correct values', () => {
    expect(AnomalySeverity.INFO).toBe('info');
    expect(AnomalySeverity.WARNING).toBe('warning');
    expect(AnomalySeverity.CRITICAL).toBe('critical');
  });
});

describe('AnomalyType enum', () => {
  it('has correct values', () => {
    expect(AnomalyType.UNUSUAL_TIME).toBe('unusual_time');
    expect(AnomalyType.UNUSUAL_FREQUENCY).toBe('unusual_frequency');
    expect(AnomalyType.UNUSUAL_DWELL).toBe('unusual_dwell');
    expect(AnomalyType.UNUSUAL_ENTITY).toBe('unusual_entity');
  });
});

describe('ANOMALY_SEVERITY_CONFIG', () => {
  it('has config for all severity levels', () => {
    expect(ANOMALY_SEVERITY_CONFIG[AnomalySeverity.INFO]).toBeDefined();
    expect(ANOMALY_SEVERITY_CONFIG[AnomalySeverity.WARNING]).toBeDefined();
    expect(ANOMALY_SEVERITY_CONFIG[AnomalySeverity.CRITICAL]).toBeDefined();
  });

  it('INFO severity has correct colors', () => {
    const config = ANOMALY_SEVERITY_CONFIG[AnomalySeverity.INFO];
    expect(config.label).toBe('Info');
    expect(config.color).toContain('blue');
    expect(config.bgColor).toContain('blue');
    expect(config.borderColor).toContain('blue');
  });

  it('WARNING severity has correct colors', () => {
    const config = ANOMALY_SEVERITY_CONFIG[AnomalySeverity.WARNING];
    expect(config.label).toBe('Warning');
    expect(config.color).toContain('yellow');
    expect(config.bgColor).toContain('yellow');
    expect(config.borderColor).toContain('yellow');
  });

  it('CRITICAL severity has correct colors', () => {
    const config = ANOMALY_SEVERITY_CONFIG[AnomalySeverity.CRITICAL];
    expect(config.label).toBe('Critical');
    expect(config.color).toContain('red');
    expect(config.bgColor).toContain('red');
    expect(config.borderColor).toContain('red');
  });
});

describe('ANOMALY_TYPE_CONFIG', () => {
  it('has config for all anomaly types', () => {
    expect(ANOMALY_TYPE_CONFIG[AnomalyType.UNUSUAL_TIME]).toBeDefined();
    expect(ANOMALY_TYPE_CONFIG[AnomalyType.UNUSUAL_FREQUENCY]).toBeDefined();
    expect(ANOMALY_TYPE_CONFIG[AnomalyType.UNUSUAL_DWELL]).toBeDefined();
    expect(ANOMALY_TYPE_CONFIG[AnomalyType.UNUSUAL_ENTITY]).toBeDefined();
  });

  it('each config has required fields', () => {
    Object.values(ANOMALY_TYPE_CONFIG).forEach((config) => {
      expect(config.label).toBeDefined();
      expect(config.description).toBeDefined();
      expect(config.icon).toBeDefined();
    });
  });
});

describe('isAnomalySeverity', () => {
  it('returns true for valid severity values', () => {
    expect(isAnomalySeverity('info')).toBe(true);
    expect(isAnomalySeverity('warning')).toBe(true);
    expect(isAnomalySeverity('critical')).toBe(true);
  });

  it('returns false for invalid values', () => {
    expect(isAnomalySeverity('invalid')).toBe(false);
    expect(isAnomalySeverity('error')).toBe(false);
    expect(isAnomalySeverity('')).toBe(false);
    expect(isAnomalySeverity(null)).toBe(false);
    expect(isAnomalySeverity(undefined)).toBe(false);
    expect(isAnomalySeverity(123)).toBe(false);
    expect(isAnomalySeverity({})).toBe(false);
  });

  it('returns false for close but incorrect values', () => {
    expect(isAnomalySeverity('INFO')).toBe(false); // Case sensitive
    expect(isAnomalySeverity('Warning')).toBe(false);
    expect(isAnomalySeverity('CRITICAL')).toBe(false);
  });
});

describe('isAnomalyType', () => {
  it('returns true for valid type values', () => {
    expect(isAnomalyType('unusual_time')).toBe(true);
    expect(isAnomalyType('unusual_frequency')).toBe(true);
    expect(isAnomalyType('unusual_dwell')).toBe(true);
    expect(isAnomalyType('unusual_entity')).toBe(true);
  });

  it('returns false for invalid values', () => {
    expect(isAnomalyType('invalid')).toBe(false);
    expect(isAnomalyType('time')).toBe(false);
    expect(isAnomalyType('')).toBe(false);
    expect(isAnomalyType(null)).toBe(false);
    expect(isAnomalyType(undefined)).toBe(false);
    expect(isAnomalyType(123)).toBe(false);
  });

  it('returns false for close but incorrect values', () => {
    expect(isAnomalyType('UNUSUAL_TIME')).toBe(false); // Case sensitive
    expect(isAnomalyType('unusual-time')).toBe(false); // Wrong delimiter
  });
});

describe('isZoneAnomaly', () => {
  const validAnomaly = {
    id: 'anomaly-123',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    anomaly_type: 'unusual_time',
    severity: 'warning',
    title: 'Test Anomaly',
    description: 'Test description',
    expected_value: 0.1,
    actual_value: 1.0,
    deviation: 3.5,
    detection_id: 12345,
    thumbnail_url: '/test.jpg',
    acknowledged: false,
    acknowledged_at: null,
    acknowledged_by: null,
    timestamp: '2024-01-15T00:00:00Z',
    created_at: '2024-01-15T00:00:00Z',
    updated_at: '2024-01-15T00:00:00Z',
  };

  it('returns true for valid ZoneAnomaly object', () => {
    expect(isZoneAnomaly(validAnomaly)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isZoneAnomaly(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isZoneAnomaly(undefined)).toBe(false);
  });

  it('returns false for non-object', () => {
    expect(isZoneAnomaly('string')).toBe(false);
    expect(isZoneAnomaly(123)).toBe(false);
    expect(isZoneAnomaly([])).toBe(false);
  });

  it('returns false when missing required fields', () => {
    expect(isZoneAnomaly({ ...validAnomaly, id: undefined })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, zone_id: undefined })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, camera_id: undefined })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, anomaly_type: undefined })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, severity: undefined })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, title: undefined })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, acknowledged: undefined })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, timestamp: undefined })).toBe(false);
  });

  it('returns false for invalid anomaly_type', () => {
    expect(isZoneAnomaly({ ...validAnomaly, anomaly_type: 'invalid' })).toBe(false);
  });

  it('returns false for invalid severity', () => {
    expect(isZoneAnomaly({ ...validAnomaly, severity: 'invalid' })).toBe(false);
  });

  it('returns false when fields have wrong types', () => {
    expect(isZoneAnomaly({ ...validAnomaly, id: 123 })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, acknowledged: 'yes' })).toBe(false);
    expect(isZoneAnomaly({ ...validAnomaly, timestamp: 123456789 })).toBe(false);
  });
});

describe('isZoneAnomalyEventPayload', () => {
  const validPayload = {
    id: 'anomaly-123',
    zone_id: 'zone-456',
    camera_id: 'cam-789',
    anomaly_type: 'unusual_time',
    severity: 'warning',
    title: 'Test Anomaly',
    description: 'Test description',
    expected_value: 0.1,
    actual_value: 1.0,
    deviation: 3.5,
    detection_id: 12345,
    thumbnail_url: '/test.jpg',
    timestamp: '2024-01-15T00:00:00Z',
  };

  it('returns true for valid payload', () => {
    expect(isZoneAnomalyEventPayload(validPayload)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isZoneAnomalyEventPayload(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isZoneAnomalyEventPayload(undefined)).toBe(false);
  });

  it('returns false for non-object', () => {
    expect(isZoneAnomalyEventPayload('string')).toBe(false);
    expect(isZoneAnomalyEventPayload(123)).toBe(false);
  });

  it('returns false when missing required fields', () => {
    expect(isZoneAnomalyEventPayload({ ...validPayload, id: undefined })).toBe(false);
    expect(isZoneAnomalyEventPayload({ ...validPayload, zone_id: undefined })).toBe(false);
    expect(isZoneAnomalyEventPayload({ ...validPayload, camera_id: undefined })).toBe(false);
    expect(isZoneAnomalyEventPayload({ ...validPayload, anomaly_type: undefined })).toBe(false);
    expect(isZoneAnomalyEventPayload({ ...validPayload, severity: undefined })).toBe(false);
    expect(isZoneAnomalyEventPayload({ ...validPayload, title: undefined })).toBe(false);
  });

  it('returns false for invalid anomaly_type', () => {
    expect(isZoneAnomalyEventPayload({ ...validPayload, anomaly_type: 'invalid' })).toBe(false);
  });

  it('returns false for invalid severity', () => {
    expect(isZoneAnomalyEventPayload({ ...validPayload, severity: 'invalid' })).toBe(false);
  });

  it('accepts payload with null optional fields', () => {
    const payloadWithNulls = {
      ...validPayload,
      description: null,
      expected_value: null,
      actual_value: null,
      deviation: null,
      detection_id: null,
      thumbnail_url: null,
      timestamp: null,
    };
    expect(isZoneAnomalyEventPayload(payloadWithNulls)).toBe(true);
  });
});
