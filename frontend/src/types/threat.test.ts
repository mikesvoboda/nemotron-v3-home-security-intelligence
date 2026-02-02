import { describe, expect, it } from 'vitest';

import {
  THREAT_TYPES,
  THREAT_SEVERITIES,
  THREAT_SEVERITY_CONFIG,
  SEVERITY_ORDER,
  isThreatType,
  isThreatSeverity,
  isThreatDetection,
  getThreatTypeLabel,
  compareSeverity,
  getMaxSeverity,
  createEmptyThreatSummary,
  createThreatSummary,
  type ThreatDetection,
} from './threat';

describe('Threat Types', () => {
  describe('THREAT_TYPES constant', () => {
    it('contains expected threat types', () => {
      expect(THREAT_TYPES).toContain('gun');
      expect(THREAT_TYPES).toContain('knife');
      expect(THREAT_TYPES).toContain('grenade');
      expect(THREAT_TYPES).toContain('explosive');
      expect(THREAT_TYPES).toContain('weapon');
      expect(THREAT_TYPES).toContain('other');
    });

    it('has 6 threat types', () => {
      expect(THREAT_TYPES).toHaveLength(6);
    });
  });

  describe('THREAT_SEVERITIES constant', () => {
    it('contains all severity levels', () => {
      expect(THREAT_SEVERITIES).toContain('critical');
      expect(THREAT_SEVERITIES).toContain('high');
      expect(THREAT_SEVERITIES).toContain('medium');
      expect(THREAT_SEVERITIES).toContain('low');
    });

    it('has 4 severity levels', () => {
      expect(THREAT_SEVERITIES).toHaveLength(4);
    });
  });

  describe('THREAT_SEVERITY_CONFIG', () => {
    it('has config for all severity levels', () => {
      for (const severity of THREAT_SEVERITIES) {
        expect(THREAT_SEVERITY_CONFIG[severity]).toBeDefined();
      }
    });

    it('critical has pulse animation', () => {
      expect(THREAT_SEVERITY_CONFIG.critical.animationClass).toBeDefined();
      expect(THREAT_SEVERITY_CONFIG.critical.animationClass).toContain('animate-pulse');
    });

    it('high has pulse animation', () => {
      expect(THREAT_SEVERITY_CONFIG.high.animationClass).toBeDefined();
    });

    it('medium does not have animation', () => {
      expect(THREAT_SEVERITY_CONFIG.medium.animationClass).toBeUndefined();
    });

    it('all configs have required properties', () => {
      for (const severity of THREAT_SEVERITIES) {
        const config = THREAT_SEVERITY_CONFIG[severity];
        expect(config.label).toBeDefined();
        expect(config.icon).toBeDefined();
        expect(config.bgColor).toBeDefined();
        expect(config.borderColor).toBeDefined();
        expect(config.textColor).toBeDefined();
      }
    });
  });

  describe('SEVERITY_ORDER', () => {
    it('critical has lowest order (most severe)', () => {
      expect(SEVERITY_ORDER.critical).toBe(0);
    });

    it('low has highest order (least severe)', () => {
      expect(SEVERITY_ORDER.low).toBe(3);
    });

    it('orders severities correctly', () => {
      expect(SEVERITY_ORDER.critical).toBeLessThan(SEVERITY_ORDER.high);
      expect(SEVERITY_ORDER.high).toBeLessThan(SEVERITY_ORDER.medium);
      expect(SEVERITY_ORDER.medium).toBeLessThan(SEVERITY_ORDER.low);
    });
  });
});

describe('Type Guards', () => {
  describe('isThreatType', () => {
    it('returns true for valid threat types', () => {
      expect(isThreatType('gun')).toBe(true);
      expect(isThreatType('knife')).toBe(true);
      expect(isThreatType('weapon')).toBe(true);
    });

    it('returns false for invalid threat types', () => {
      expect(isThreatType('invalid')).toBe(false);
      expect(isThreatType('')).toBe(false);
      expect(isThreatType(null)).toBe(false);
      expect(isThreatType(undefined)).toBe(false);
      expect(isThreatType(123)).toBe(false);
    });
  });

  describe('isThreatSeverity', () => {
    it('returns true for valid severities', () => {
      expect(isThreatSeverity('critical')).toBe(true);
      expect(isThreatSeverity('high')).toBe(true);
      expect(isThreatSeverity('medium')).toBe(true);
      expect(isThreatSeverity('low')).toBe(true);
    });

    it('returns false for invalid severities', () => {
      expect(isThreatSeverity('invalid')).toBe(false);
      expect(isThreatSeverity('urgent')).toBe(false);
      expect(isThreatSeverity(null)).toBe(false);
      expect(isThreatSeverity(undefined)).toBe(false);
    });
  });

  describe('isThreatDetection', () => {
    it('returns true for valid threat detection', () => {
      const detection: ThreatDetection = {
        threat_type: 'gun',
        confidence: 0.95,
        severity: 'critical',
      };
      expect(isThreatDetection(detection)).toBe(true);
    });

    it('returns true with optional fields', () => {
      const detection: ThreatDetection = {
        id: 1,
        threat_type: 'knife',
        confidence: 0.8,
        severity: 'high',
        bbox: [100, 100, 200, 200],
        camera_id: 'front_door',
        event_id: 123,
      };
      expect(isThreatDetection(detection)).toBe(true);
    });

    it('returns false for invalid objects', () => {
      expect(isThreatDetection(null)).toBe(false);
      expect(isThreatDetection(undefined)).toBe(false);
      expect(isThreatDetection({})).toBe(false);
      expect(isThreatDetection({ threat_type: 'gun' })).toBe(false);
      expect(isThreatDetection({ threat_type: 'gun', confidence: 0.5 })).toBe(false);
    });

    it('returns false for invalid confidence', () => {
      expect(
        isThreatDetection({ threat_type: 'gun', confidence: -0.1, severity: 'critical' })
      ).toBe(false);
      expect(
        isThreatDetection({ threat_type: 'gun', confidence: 1.5, severity: 'critical' })
      ).toBe(false);
    });

    it('returns false for invalid severity', () => {
      expect(
        isThreatDetection({ threat_type: 'gun', confidence: 0.5, severity: 'invalid' })
      ).toBe(false);
    });
  });
});

describe('Utility Functions', () => {
  describe('getThreatTypeLabel', () => {
    it('returns human-readable label for known types', () => {
      expect(getThreatTypeLabel('gun')).toBe('Firearm');
      expect(getThreatTypeLabel('knife')).toBe('Knife/Blade');
      expect(getThreatTypeLabel('grenade')).toBe('Grenade');
      expect(getThreatTypeLabel('explosive')).toBe('Explosive Device');
      expect(getThreatTypeLabel('weapon')).toBe('Weapon');
      expect(getThreatTypeLabel('other')).toBe('Unknown Threat');
    });

    it('capitalizes unknown types', () => {
      expect(getThreatTypeLabel('custom')).toBe('Custom');
      expect(getThreatTypeLabel('machete')).toBe('Machete');
    });
  });

  describe('compareSeverity', () => {
    it('returns negative when first is more severe', () => {
      expect(compareSeverity('critical', 'high')).toBeLessThan(0);
      expect(compareSeverity('high', 'medium')).toBeLessThan(0);
      expect(compareSeverity('critical', 'low')).toBeLessThan(0);
    });

    it('returns positive when first is less severe', () => {
      expect(compareSeverity('low', 'critical')).toBeGreaterThan(0);
      expect(compareSeverity('medium', 'high')).toBeGreaterThan(0);
    });

    it('returns 0 for same severity', () => {
      expect(compareSeverity('critical', 'critical')).toBe(0);
      expect(compareSeverity('medium', 'medium')).toBe(0);
    });
  });

  describe('getMaxSeverity', () => {
    it('returns null for empty array', () => {
      expect(getMaxSeverity([])).toBeNull();
    });

    it('returns the single severity for one-element array', () => {
      expect(getMaxSeverity(['medium'])).toBe('medium');
    });

    it('returns most severe from multiple severities', () => {
      expect(getMaxSeverity(['medium', 'high', 'low'])).toBe('high');
      expect(getMaxSeverity(['low', 'critical', 'medium'])).toBe('critical');
    });

    it('handles duplicates', () => {
      expect(getMaxSeverity(['high', 'high', 'medium'])).toBe('high');
    });
  });
});

describe('Threat Summary Functions', () => {
  describe('createEmptyThreatSummary', () => {
    it('returns empty summary with correct defaults', () => {
      const summary = createEmptyThreatSummary();

      expect(summary.hasActiveThreats).toBe(false);
      expect(summary.totalThreats).toBe(0);
      expect(summary.maxSeverity).toBeNull();
      expect(summary.threats).toEqual([]);
      expect(summary.criticalCount).toBe(0);
      expect(summary.highCount).toBe(0);
      expect(summary.mediumCount).toBe(0);
      expect(summary.latestThreat).toBeNull();
      expect(summary.threatTypes).toEqual([]);
      expect(summary.affectedCameras).toEqual([]);
    });
  });

  describe('createThreatSummary', () => {
    it('returns empty summary for empty array', () => {
      const summary = createThreatSummary([]);
      expect(summary.hasActiveThreats).toBe(false);
    });

    it('calculates correct counts', () => {
      const threats: ThreatDetection[] = [
        { id: 1, threat_type: 'gun', confidence: 0.9, severity: 'critical' },
        { id: 2, threat_type: 'knife', confidence: 0.8, severity: 'high' },
        { id: 3, threat_type: 'gun', confidence: 0.85, severity: 'critical' },
        { id: 4, threat_type: 'weapon', confidence: 0.7, severity: 'medium' },
      ];

      const summary = createThreatSummary(threats);

      expect(summary.hasActiveThreats).toBe(true);
      expect(summary.totalThreats).toBe(4);
      expect(summary.criticalCount).toBe(2);
      expect(summary.highCount).toBe(1);
      expect(summary.mediumCount).toBe(1);
    });

    it('identifies max severity', () => {
      const threats: ThreatDetection[] = [
        { id: 1, threat_type: 'weapon', confidence: 0.7, severity: 'medium' },
        { id: 2, threat_type: 'knife', confidence: 0.8, severity: 'high' },
        { id: 3, threat_type: 'weapon', confidence: 0.6, severity: 'low' },
      ];

      const summary = createThreatSummary(threats);
      expect(summary.maxSeverity).toBe('high');
    });

    it('collects unique threat types', () => {
      const threats: ThreatDetection[] = [
        { id: 1, threat_type: 'gun', confidence: 0.9, severity: 'critical' },
        { id: 2, threat_type: 'knife', confidence: 0.8, severity: 'high' },
        { id: 3, threat_type: 'gun', confidence: 0.85, severity: 'critical' },
      ];

      const summary = createThreatSummary(threats);
      expect(summary.threatTypes).toEqual(['gun', 'knife']);
    });

    it('collects affected cameras', () => {
      const threats: ThreatDetection[] = [
        { id: 1, threat_type: 'gun', confidence: 0.9, severity: 'critical', camera_id: 'front' },
        { id: 2, threat_type: 'knife', confidence: 0.8, severity: 'high', camera_id: 'back' },
        { id: 3, threat_type: 'gun', confidence: 0.85, severity: 'critical', camera_id: 'front' },
      ];

      const summary = createThreatSummary(threats);
      expect(summary.affectedCameras).toEqual(['front', 'back']);
    });

    it('identifies latest threat by created_at', () => {
      const threats: ThreatDetection[] = [
        {
          id: 1,
          threat_type: 'gun',
          confidence: 0.9,
          severity: 'critical',
          created_at: '2024-01-01T10:00:00Z',
        },
        {
          id: 2,
          threat_type: 'knife',
          confidence: 0.8,
          severity: 'high',
          created_at: '2024-01-01T12:00:00Z',
        },
        {
          id: 3,
          threat_type: 'weapon',
          confidence: 0.7,
          severity: 'medium',
          created_at: '2024-01-01T11:00:00Z',
        },
      ];

      const summary = createThreatSummary(threats);
      expect(summary.latestThreat?.id).toBe(2);
    });
  });
});
