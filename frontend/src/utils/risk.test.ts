import { describe, expect, it } from 'vitest';

import { getRiskColor, getRiskLabel, getRiskLevel } from './risk';

describe('risk utilities', () => {
  describe('getRiskLevel', () => {
    it('returns "low" for scores 0-25', () => {
      expect(getRiskLevel(0)).toBe('low');
      expect(getRiskLevel(10)).toBe('low');
      expect(getRiskLevel(25)).toBe('low');
    });

    it('returns "medium" for scores 26-50', () => {
      expect(getRiskLevel(26)).toBe('medium');
      expect(getRiskLevel(40)).toBe('medium');
      expect(getRiskLevel(50)).toBe('medium');
    });

    it('returns "high" for scores 51-75', () => {
      expect(getRiskLevel(51)).toBe('high');
      expect(getRiskLevel(65)).toBe('high');
      expect(getRiskLevel(75)).toBe('high');
    });

    it('returns "critical" for scores 76-100', () => {
      expect(getRiskLevel(76)).toBe('critical');
      expect(getRiskLevel(90)).toBe('critical');
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
    it('returns green for low risk', () => {
      expect(getRiskColor('low')).toBe('#22c55e');
    });

    it('returns yellow for medium risk', () => {
      expect(getRiskColor('medium')).toBe('#eab308');
    });

    it('returns orange for high risk', () => {
      expect(getRiskColor('high')).toBe('#f97316');
    });

    it('returns red for critical risk', () => {
      expect(getRiskColor('critical')).toBe('#ef4444');
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
});
