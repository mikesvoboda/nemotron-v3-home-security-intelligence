/**
 * Tests for Zone Crossing Types (NEM-3195)
 *
 * This module tests the zone crossing type definitions and utility functions:
 * - Type guards
 * - formatDwellTime utility
 * - Configuration constants
 */

import { describe, it, expect } from 'vitest';

import {
  ZoneCrossingType,
  ZONE_CROSSING_TYPE_CONFIG,
  ENTITY_TYPE_CONFIG,
  isZoneCrossingType,
  isZoneCrossingEventPayload,
  isZoneCrossingEvent,
  formatDwellTime,
} from './zoneCrossing';

import type { ZoneCrossingEvent, ZoneCrossingEventPayload } from './zoneCrossing';

describe('ZoneCrossingType enum', () => {
  it('has the expected values', () => {
    expect(ZoneCrossingType.ENTER).toBe('enter');
    expect(ZoneCrossingType.EXIT).toBe('exit');
    expect(ZoneCrossingType.DWELL).toBe('dwell');
  });

  it('has exactly three values', () => {
    expect(Object.values(ZoneCrossingType)).toHaveLength(3);
  });
});

describe('ZONE_CROSSING_TYPE_CONFIG', () => {
  it('has configuration for all crossing types', () => {
    expect(ZONE_CROSSING_TYPE_CONFIG[ZoneCrossingType.ENTER]).toBeDefined();
    expect(ZONE_CROSSING_TYPE_CONFIG[ZoneCrossingType.EXIT]).toBeDefined();
    expect(ZONE_CROSSING_TYPE_CONFIG[ZoneCrossingType.DWELL]).toBeDefined();
  });

  it('has required properties for each configuration', () => {
    Object.values(ZONE_CROSSING_TYPE_CONFIG).forEach((config) => {
      expect(config).toHaveProperty('label');
      expect(config).toHaveProperty('description');
      expect(config).toHaveProperty('color');
      expect(config).toHaveProperty('bgColor');
      expect(config).toHaveProperty('borderColor');
      expect(config).toHaveProperty('icon');
    });
  });

  it('uses green colors for ENTER', () => {
    const config = ZONE_CROSSING_TYPE_CONFIG[ZoneCrossingType.ENTER];
    expect(config.color).toContain('green');
    expect(config.bgColor).toContain('green');
  });

  it('uses red colors for EXIT', () => {
    const config = ZONE_CROSSING_TYPE_CONFIG[ZoneCrossingType.EXIT];
    expect(config.color).toContain('red');
    expect(config.bgColor).toContain('red');
  });

  it('uses orange colors for DWELL', () => {
    const config = ZONE_CROSSING_TYPE_CONFIG[ZoneCrossingType.DWELL];
    expect(config.color).toContain('orange');
    expect(config.bgColor).toContain('orange');
  });
});

describe('ENTITY_TYPE_CONFIG', () => {
  it('has configuration for common entity types', () => {
    expect(ENTITY_TYPE_CONFIG['person']).toBeDefined();
    expect(ENTITY_TYPE_CONFIG['vehicle']).toBeDefined();
    expect(ENTITY_TYPE_CONFIG['unknown']).toBeDefined();
  });

  it('has required properties for each configuration', () => {
    Object.values(ENTITY_TYPE_CONFIG).forEach((config) => {
      expect(config).toHaveProperty('label');
      expect(config).toHaveProperty('icon');
    });
  });
});

describe('isZoneCrossingType', () => {
  it('returns true for valid crossing types', () => {
    expect(isZoneCrossingType('enter')).toBe(true);
    expect(isZoneCrossingType('exit')).toBe(true);
    expect(isZoneCrossingType('dwell')).toBe(true);
  });

  it('returns true for enum values', () => {
    expect(isZoneCrossingType(ZoneCrossingType.ENTER)).toBe(true);
    expect(isZoneCrossingType(ZoneCrossingType.EXIT)).toBe(true);
    expect(isZoneCrossingType(ZoneCrossingType.DWELL)).toBe(true);
  });

  it('returns false for invalid values', () => {
    expect(isZoneCrossingType('invalid')).toBe(false);
    expect(isZoneCrossingType('ENTER')).toBe(false);
    expect(isZoneCrossingType('')).toBe(false);
    expect(isZoneCrossingType(null)).toBe(false);
    expect(isZoneCrossingType(undefined)).toBe(false);
    expect(isZoneCrossingType(123)).toBe(false);
    expect(isZoneCrossingType({})).toBe(false);
    expect(isZoneCrossingType([])).toBe(false);
  });
});

describe('isZoneCrossingEventPayload', () => {
  const validPayload: ZoneCrossingEventPayload = {
    zone_id: 'zone-1',
    zone_name: 'Front Door',
    entity_id: 'entity-123',
    entity_type: 'person',
    detection_id: 'det-456',
    timestamp: '2024-01-01T12:00:00Z',
  };

  it('returns true for valid payload', () => {
    expect(isZoneCrossingEventPayload(validPayload)).toBe(true);
  });

  it('returns true for payload with optional fields', () => {
    const payloadWithOptional = {
      ...validPayload,
      thumbnail_url: 'http://example.com/thumb.jpg',
      dwell_time: 30,
    };
    expect(isZoneCrossingEventPayload(payloadWithOptional)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isZoneCrossingEventPayload(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isZoneCrossingEventPayload(undefined)).toBe(false);
  });

  it('returns false for non-objects', () => {
    expect(isZoneCrossingEventPayload('string')).toBe(false);
    expect(isZoneCrossingEventPayload(123)).toBe(false);
    expect(isZoneCrossingEventPayload([])).toBe(false);
  });

  it('returns false for missing zone_id', () => {
    const { zone_id: _, ...payload } = validPayload;
    expect(isZoneCrossingEventPayload(payload)).toBe(false);
  });

  it('returns false for missing zone_name', () => {
    const { zone_name: _, ...payload } = validPayload;
    expect(isZoneCrossingEventPayload(payload)).toBe(false);
  });

  it('returns false for missing entity_id', () => {
    const { entity_id: _, ...payload } = validPayload;
    expect(isZoneCrossingEventPayload(payload)).toBe(false);
  });

  it('returns false for missing entity_type', () => {
    const { entity_type: _, ...payload } = validPayload;
    expect(isZoneCrossingEventPayload(payload)).toBe(false);
  });

  it('returns false for missing detection_id', () => {
    const { detection_id: _, ...payload } = validPayload;
    expect(isZoneCrossingEventPayload(payload)).toBe(false);
  });

  it('returns false for missing timestamp', () => {
    const { timestamp: _, ...payload } = validPayload;
    expect(isZoneCrossingEventPayload(payload)).toBe(false);
  });

  it('returns false for wrong types', () => {
    expect(
      isZoneCrossingEventPayload({
        ...validPayload,
        zone_id: 123,
      })
    ).toBe(false);
  });
});

describe('isZoneCrossingEvent', () => {
  const validEvent: ZoneCrossingEvent = {
    type: ZoneCrossingType.ENTER,
    zone_id: 'zone-1',
    zone_name: 'Front Door',
    entity_id: 'entity-123',
    entity_type: 'person',
    detection_id: 'det-456',
    timestamp: '2024-01-01T12:00:00Z',
  };

  it('returns true for valid event', () => {
    expect(isZoneCrossingEvent(validEvent)).toBe(true);
  });

  it('returns true for all event types', () => {
    expect(isZoneCrossingEvent({ ...validEvent, type: ZoneCrossingType.ENTER })).toBe(true);
    expect(isZoneCrossingEvent({ ...validEvent, type: ZoneCrossingType.EXIT })).toBe(true);
    expect(isZoneCrossingEvent({ ...validEvent, type: ZoneCrossingType.DWELL })).toBe(true);
  });

  it('returns true for event with optional fields', () => {
    const eventWithOptional = {
      ...validEvent,
      thumbnail_url: 'http://example.com/thumb.jpg',
      dwell_time: 30,
    };
    expect(isZoneCrossingEvent(eventWithOptional)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isZoneCrossingEvent(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isZoneCrossingEvent(undefined)).toBe(false);
  });

  it('returns false for invalid type', () => {
    const invalidEvent = {
      ...validEvent,
      type: 'invalid',
    };
    expect(isZoneCrossingEvent(invalidEvent)).toBe(false);
  });

  it('returns false for missing type', () => {
    const { type: _, ...event } = validEvent;
    expect(isZoneCrossingEvent(event)).toBe(false);
  });

  it('returns false for missing required fields', () => {
    const { zone_id: _, ...event } = validEvent;
    expect(isZoneCrossingEvent(event)).toBe(false);
  });
});

describe('formatDwellTime', () => {
  it('returns "--" for null', () => {
    expect(formatDwellTime(null)).toBe('--');
  });

  it('returns "--" for undefined', () => {
    expect(formatDwellTime(undefined)).toBe('--');
  });

  it('formats seconds only', () => {
    expect(formatDwellTime(0)).toBe('0s');
    expect(formatDwellTime(1)).toBe('1s');
    expect(formatDwellTime(30)).toBe('30s');
    expect(formatDwellTime(59)).toBe('59s');
  });

  it('formats minutes and seconds', () => {
    expect(formatDwellTime(60)).toBe('1m 0s');
    expect(formatDwellTime(90)).toBe('1m 30s');
    expect(formatDwellTime(125)).toBe('2m 5s');
    expect(formatDwellTime(3599)).toBe('59m 59s');
  });

  it('formats hours and minutes', () => {
    expect(formatDwellTime(3600)).toBe('1h 0m');
    expect(formatDwellTime(3660)).toBe('1h 1m');
    expect(formatDwellTime(7200)).toBe('2h 0m');
    expect(formatDwellTime(7320)).toBe('2h 2m');
  });

  it('handles large values', () => {
    expect(formatDwellTime(36000)).toBe('10h 0m');
    expect(formatDwellTime(86400)).toBe('24h 0m');
  });

  it('handles decimal values by flooring', () => {
    expect(formatDwellTime(30.5)).toBe('30s');
    expect(formatDwellTime(90.9)).toBe('1m 30s');
  });
});
