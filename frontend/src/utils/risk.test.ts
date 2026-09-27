import { describe, expect, it } from 'vitest';

import {
  compareRiskSortKey,
  getRiskBgClass,
  getRiskColor,
  getRiskLabel,
  getRiskLevel,
  getRiskLevelWithThresholds,
  getRiskTextClass,
  resolveRiskLevel,
  riskSortKey,
  RISK_THRESHOLDS,
} from './risk';

describe('risk utilities', () => {
  describe('getRiskLevel', () => {
    // Thresholds match backend defaults (see backend/core/config.py):
    // LOW: 0-29, MEDIUM: 30-59, HIGH: 60-84, CRITICAL: 85-100
    it('returns "low" for scores 0-29', () => {
      expect(getRiskLevel(0)).toBe('low');
      expect(getRiskLevel(15)).toBe('low');
      expect(getRiskLevel(29)).toBe('low');
    });

    it('returns "medium" for scores 30-59', () => {
      expect(getRiskLevel(30)).toBe('medium');
      expect(getRiskLevel(45)).toBe('medium');
      expect(getRiskLevel(59)).toBe('medium');
    });

    it('returns "high" for scores 60-84', () => {
      expect(getRiskLevel(60)).toBe('high');
      expect(getRiskLevel(70)).toBe('high');
      expect(getRiskLevel(84)).toBe('high');
    });

    it('returns "critical" for scores 85-100', () => {
      expect(getRiskLevel(85)).toBe('critical');
      expect(getRiskLevel(92)).toBe('critical');
      expect(getRiskLevel(100)).toBe('critical');
    });

    it('throws error for negative scores', () => {
      expect(() => getRiskLevel(-1)).toThrow('Risk score must be between 0 and 100');
      expect(() => getRiskLevel(-10)).toThrow('Risk score must be between 0 and 100');
    });

    it('throws error for scores above 100', () => {
      expect(() => getRiskLevel(101)).toThrow('Risk score must be between 0 and 100');
      expect(() => getRiskLevel(150)).toThrow('Risk score must be between 0 and 100');
    });
  });

  describe('getRiskColor', () => {
    // Colors use Tailwind CSS standard severity colors for clear visual differentiation
    it('returns green-500 (#22c55e) for low risk', () => {
      expect(getRiskColor('low')).toBe('#22c55e');
    });

    it('returns yellow-500 (#eab308) for medium risk', () => {
      expect(getRiskColor('medium')).toBe('#eab308');
    });

    it('returns orange-500 (#f97316) for high risk', () => {
      expect(getRiskColor('high')).toBe('#f97316');
    });

    it('returns red-500 (#ef4444) for critical risk', () => {
      expect(getRiskColor('critical')).toBe('#ef4444');
    });
  });

  describe('getRiskBgClass', () => {
    it('returns bg-green-500 for low risk', () => {
      expect(getRiskBgClass('low')).toBe('bg-green-500');
    });

    it('returns bg-yellow-500 for medium risk', () => {
      expect(getRiskBgClass('medium')).toBe('bg-yellow-500');
    });

    it('returns bg-orange-500 for high risk', () => {
      expect(getRiskBgClass('high')).toBe('bg-orange-500');
    });

    it('returns bg-red-500 for critical risk', () => {
      expect(getRiskBgClass('critical')).toBe('bg-red-500');
    });
  });

  describe('getRiskTextClass', () => {
    it('returns text-green-500 for low risk', () => {
      expect(getRiskTextClass('low')).toBe('text-green-500');
    });

    it('returns text-yellow-500 for medium risk', () => {
      expect(getRiskTextClass('medium')).toBe('text-yellow-500');
    });

    it('returns text-orange-500 for high risk', () => {
      expect(getRiskTextClass('high')).toBe('text-orange-500');
    });

    it('returns text-red-500 for critical risk', () => {
      expect(getRiskTextClass('critical')).toBe('text-red-500');
    });
  });

  describe('getRiskLabel', () => {
    it('returns "Low" for low risk level', () => {
      expect(getRiskLabel('low')).toBe('Low');
    });

    it('returns "Medium" for medium risk level', () => {
      expect(getRiskLabel('medium')).toBe('Medium');
    });

    it('returns "High" for high risk level', () => {
      expect(getRiskLabel('high')).toBe('High');
    });

    it('returns "Critical" for critical risk level', () => {
      expect(getRiskLabel('critical')).toBe('Critical');
    });
  });

  describe('RISK_THRESHOLDS', () => {
    it('exports default thresholds matching backend SeverityService', () => {
      expect(RISK_THRESHOLDS.LOW_MAX).toBe(29);
      expect(RISK_THRESHOLDS.MEDIUM_MAX).toBe(59);
      expect(RISK_THRESHOLDS.HIGH_MAX).toBe(84);
    });
  });

  describe('getRiskLevelWithThresholds', () => {
    const customThresholds = { low_max: 20, medium_max: 50, high_max: 80 };

    it('uses custom thresholds for low risk', () => {
      // score 0 must NOT throw: the guard is `score < 0`, not `score <= 0`
      // (measured shipped behavior — kills the stryker EqualityOperator
      // survivor at risk.ts:57).
      expect(getRiskLevelWithThresholds(0, customThresholds)).toBe('low');
      expect(getRiskLevelWithThresholds(20, customThresholds)).toBe('low');
      expect(getRiskLevelWithThresholds(21, customThresholds)).toBe('medium');
    });

    it('uses custom thresholds for medium risk', () => {
      expect(getRiskLevelWithThresholds(50, customThresholds)).toBe('medium');
      expect(getRiskLevelWithThresholds(51, customThresholds)).toBe('high');
    });

    it('uses custom thresholds for high risk', () => {
      expect(getRiskLevelWithThresholds(80, customThresholds)).toBe('high');
      expect(getRiskLevelWithThresholds(81, customThresholds)).toBe('critical');
    });

    it('uses custom thresholds for critical risk', () => {
      expect(getRiskLevelWithThresholds(81, customThresholds)).toBe('critical');
      expect(getRiskLevelWithThresholds(100, customThresholds)).toBe('critical');
    });

    it('throws error for out of range scores', () => {
      expect(() => getRiskLevelWithThresholds(-1, customThresholds)).toThrow(
        'Risk score must be between 0 and 100'
      );
      expect(() => getRiskLevelWithThresholds(101, customThresholds)).toThrow(
        'Risk score must be between 0 and 100'
      );
    });
  });

  describe('resolveRiskLevel (1.6 null-safe rendering)', () => {
    it('prefers the server-computed risk_level over the score', () => {
      // The server level already carries SeverityService thresholds; a
      // client recomputation from the score could disagree with them.
      expect(resolveRiskLevel('high', 10)).toBe('high');
    });

    it('falls back to the score when no level is present', () => {
      expect(resolveRiskLevel(null, 45)).toBe('medium');
      expect(resolveRiskLevel(undefined, 90)).toBe('critical');
    });

    it('returns null - NOT "low" - for a NULL score with no level', () => {
      // The null-lie this replaces: `getRiskLevel(score || 0)` rendered a
      // verification_failed event (NULL score, D11) as a confident green
      // "Low" badge. No score means no level; the caller shows Unverified.
      expect(resolveRiskLevel(null, null)).toBeNull();
      expect(resolveRiskLevel(undefined, undefined)).toBeNull();
      expect(resolveRiskLevel('', null)).toBeNull();
    });

    it('a real score of 0 is still "low" (null and zero are different)', () => {
      expect(resolveRiskLevel(null, 0)).toBe('low');
    });
  });

  describe('riskSortKey (1.6)', () => {
    it('scores sort among themselves', () => {
      expect(riskSortKey(10) - riskSortKey(50)).toBe(-40);
    });

    it('NULL sorts above every score descending (unknown is not safe)', () => {
      // `risk_score || 0` made an unverified event sort as the LOWEST risk,
      // burying never-analyzed events at the bottom of a worst-first list.
      // Unknown must not masquerade as safe.
      expect(riskSortKey(null) > riskSortKey(100)).toBe(true);
      expect(riskSortKey(undefined) > riskSortKey(100)).toBe(true);
    });

    it('a real score of 0 sorts lowest (null and zero stay different)', () => {
      expect(riskSortKey(0) < riskSortKey(50)).toBe(true);
    });
  });

  describe('compareRiskSortKey (1.6)', () => {
    it('two unverified events compare EQUAL, not NaN', () => {
      // The list comparator this replaces was `key(a) - key(b)`, and
      // Infinity - Infinity is NaN - two unknowns side by side poison the
      // sort result for the whole array.
      expect(compareRiskSortKey(null, null)).toBe(0);
      expect(compareRiskSortKey(undefined, null)).toBe(0);
    });

    it('scores compare among themselves', () => {
      expect(compareRiskSortKey(10, 50)).toBe(-1);
      expect(compareRiskSortKey(50, 10)).toBe(1);
      expect(compareRiskSortKey(50, 50)).toBe(0);
    });

    it('unverified outranks every score worst-first', () => {
      expect(compareRiskSortKey(null, 100)).toBe(1);
      expect(compareRiskSortKey(100, null)).toBe(-1);
    });

    it('sorts a real mixed list: worst first, unknowns on top, stable among unknowns', () => {
      const scores: (number | null)[] = [40, null, 90, null, 0];
      const worstFirst = [...scores].sort(
        (a, b) => -compareRiskSortKey(a, b) // negated: descending = worst first
      );
      // Unknowns first (they need eyes), then 90, 40, 0.
      expect(worstFirst.slice(0, 2)).toEqual([null, null]);
      expect(worstFirst.slice(2)).toEqual([90, 40, 0]);
    });
  });
});
