/**
 * Tests for severity types and default values.
 */

import { describe, expect, it } from 'vitest';

import {
  DEFAULT_SEVERITY_DEFINITIONS,
  DEFAULT_SEVERITY_THRESHOLDS,
} from './severity';

import type {
  SeverityDefinition,
  SeverityLevel,
  SeverityMetadata,
  SeverityThresholds,
} from './severity';

describe('severity types', () => {
  describe('DEFAULT_SEVERITY_THRESHOLDS', () => {
    it('matches backend default values', () => {
      expect(DEFAULT_SEVERITY_THRESHOLDS.low_max).toBe(29);
      expect(DEFAULT_SEVERITY_THRESHOLDS.medium_max).toBe(59);
      expect(DEFAULT_SEVERITY_THRESHOLDS.high_max).toBe(84);
    });

    it('has correct type structure', () => {
      const thresholds: SeverityThresholds = DEFAULT_SEVERITY_THRESHOLDS;
      expect(typeof thresholds.low_max).toBe('number');
      expect(typeof thresholds.medium_max).toBe('number');
      expect(typeof thresholds.high_max).toBe('number');
    });

    it('thresholds are in ascending order', () => {
      expect(DEFAULT_SEVERITY_THRESHOLDS.low_max).toBeLessThan(
        DEFAULT_SEVERITY_THRESHOLDS.medium_max
      );
      expect(DEFAULT_SEVERITY_THRESHOLDS.medium_max).toBeLessThan(
        DEFAULT_SEVERITY_THRESHOLDS.high_max
      );
      expect(DEFAULT_SEVERITY_THRESHOLDS.high_max).toBeLessThan(100);
    });
  });

  describe('DEFAULT_SEVERITY_DEFINITIONS', () => {
    it('has all four severity levels', () => {
      expect(DEFAULT_SEVERITY_DEFINITIONS).toHaveLength(4);

      const levels = DEFAULT_SEVERITY_DEFINITIONS.map((d) => d.severity);
      expect(levels).toContain('low');
      expect(levels).toContain('medium');
      expect(levels).toContain('high');
      expect(levels).toContain('critical');
    });

    it('each definition has required properties', () => {
      DEFAULT_SEVERITY_DEFINITIONS.forEach((def: SeverityDefinition) => {
        expect(def).toHaveProperty('severity');
        expect(def).toHaveProperty('label');
        expect(def).toHaveProperty('description');
        expect(def).toHaveProperty('color');
        expect(def).toHaveProperty('priority');
        expect(def).toHaveProperty('min_score');
        expect(def).toHaveProperty('max_score');
      });
    });

    it('definitions have valid Tailwind color hex codes', () => {
      const colorPattern = /^#[0-9a-f]{6}$/i;
      DEFAULT_SEVERITY_DEFINITIONS.forEach((def) => {
        expect(def.color).toMatch(colorPattern);
      });
    });

    it('definitions have contiguous non-overlapping score ranges', () => {
      // Sort by min_score to ensure order
      const sorted = [...DEFAULT_SEVERITY_DEFINITIONS].sort(
        (a, b) => a.min_score - b.min_score
      );

      // First should start at 0
      expect(sorted[0].min_score).toBe(0);

      // Last should end at 100
      expect(sorted[sorted.length - 1].max_score).toBe(100);

      // Each subsequent definition should start where the previous ended + 1
      for (let i = 1; i < sorted.length; i++) {
        expect(sorted[i].min_score).toBe(sorted[i - 1].max_score + 1);
      }
    });

    it('priorities are ascending with severity', () => {
      const low = DEFAULT_SEVERITY_DEFINITIONS.find((d) => d.severity === 'low');
      const medium = DEFAULT_SEVERITY_DEFINITIONS.find((d) => d.severity === 'medium');
      const high = DEFAULT_SEVERITY_DEFINITIONS.find((d) => d.severity === 'high');
      const critical = DEFAULT_SEVERITY_DEFINITIONS.find((d) => d.severity === 'critical');

      expect(low!.priority).toBeLessThan(medium!.priority);
      expect(medium!.priority).toBeLessThan(high!.priority);
      expect(high!.priority).toBeLessThan(critical!.priority);
    });

    it('definitions align with thresholds', () => {
      const low = DEFAULT_SEVERITY_DEFINITIONS.find((d) => d.severity === 'low');
      const medium = DEFAULT_SEVERITY_DEFINITIONS.find((d) => d.severity === 'medium');
      const high = DEFAULT_SEVERITY_DEFINITIONS.find((d) => d.severity === 'high');

      expect(low!.max_score).toBe(DEFAULT_SEVERITY_THRESHOLDS.low_max);
      expect(medium!.max_score).toBe(DEFAULT_SEVERITY_THRESHOLDS.medium_max);
      expect(high!.max_score).toBe(DEFAULT_SEVERITY_THRESHOLDS.high_max);
    });
  });

  describe('type compatibility', () => {
    it('SeverityLevel type accepts valid values', () => {
      const levels: SeverityLevel[] = ['low', 'medium', 'high', 'critical'];
      expect(levels).toHaveLength(4);
    });

    it('SeverityMetadata can be constructed', () => {
      const metadata: SeverityMetadata = {
        definitions: DEFAULT_SEVERITY_DEFINITIONS,
        thresholds: DEFAULT_SEVERITY_THRESHOLDS,
      };

      expect(metadata.definitions).toHaveLength(4);
      expect(metadata.thresholds.low_max).toBe(29);
    });
  });
});
