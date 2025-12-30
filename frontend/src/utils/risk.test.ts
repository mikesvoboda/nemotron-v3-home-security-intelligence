import { describe, expect, it } from 'vitest';

import { getRiskColor, getRiskLabel, getRiskLevel, getRiskLevelWithThresholds, RISK_THRESHOLDS } from './risk';

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
    it('returns NVIDIA green for low risk', () => {
      expect(getRiskColor('low')).toBe('#76B900');
    });

    it('returns NVIDIA yellow for medium risk', () => {
      expect(getRiskColor('medium')).toBe('#FFB800');
    });

    it('returns NVIDIA red for high risk', () => {
      expect(getRiskColor('high')).toBe('#E74856');
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
      expect(() => getRiskLevelWithThresholds(-1, customThresholds)).toThrow('Risk score must be between 0 and 100');
      expect(() => getRiskLevelWithThresholds(101, customThresholds)).toThrow('Risk score must be between 0 and 100');
    });
  });
});
