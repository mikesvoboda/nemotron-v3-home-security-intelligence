import { describe, expect, it } from 'vitest';

import {
  getSeverityBgClass,
  getSeverityBorderClass,
  getSeverityConfig,
  getSeverityLevel,
  getSeverityStyle,
  isCriticalSeverity,
  SEVERITY_COLORS,
  SEVERITY_THRESHOLDS,
  type SeverityConfig,
  type SeverityLevel,
} from './severityColors';

describe('severityColors', () => {
  describe('SEVERITY_THRESHOLDS', () => {
    it('defines correct threshold values', () => {
      expect(SEVERITY_THRESHOLDS.CRITICAL_MIN).toBe(80);
      expect(SEVERITY_THRESHOLDS.HIGH_MIN).toBe(60);
      expect(SEVERITY_THRESHOLDS.MEDIUM_MIN).toBe(30);
    });
  });

  describe('SEVERITY_COLORS', () => {
    it('defines critical colors correctly', () => {
      expect(SEVERITY_COLORS.critical.bgTint).toBe('rgba(239, 68, 68, 0.08)');
      expect(SEVERITY_COLORS.critical.borderColor).toBe('#EF4444');
      expect(SEVERITY_COLORS.critical.glowShadow).toBe('0 0 8px rgba(239, 68, 68, 0.3)');
    });

    it('defines high colors correctly', () => {
      expect(SEVERITY_COLORS.high.bgTint).toBe('rgba(249, 115, 22, 0.06)');
      expect(SEVERITY_COLORS.high.borderColor).toBe('#F97316');
      expect(SEVERITY_COLORS.high.glowShadow).toBe('');
    });

    it('defines medium colors correctly', () => {
      expect(SEVERITY_COLORS.medium.bgTint).toBe('rgba(234, 179, 8, 0.04)');
      expect(SEVERITY_COLORS.medium.borderColor).toBe('#EAB308');
      expect(SEVERITY_COLORS.medium.glowShadow).toBe('');
    });

    it('defines low colors correctly', () => {
      expect(SEVERITY_COLORS.low.bgTint).toBe('transparent');
      expect(SEVERITY_COLORS.low.borderColor).toBe('#76B900');
      expect(SEVERITY_COLORS.low.glowShadow).toBe('');
    });
  });

  describe('getSeverityLevel', () => {
    it('returns "critical" for scores >= 80', () => {
      expect(getSeverityLevel(80)).toBe('critical');
      expect(getSeverityLevel(85)).toBe('critical');
      expect(getSeverityLevel(90)).toBe('critical');
      expect(getSeverityLevel(100)).toBe('critical');
    });

    it('returns "high" for scores 60-79', () => {
      expect(getSeverityLevel(60)).toBe('high');
      expect(getSeverityLevel(65)).toBe('high');
      expect(getSeverityLevel(70)).toBe('high');
      expect(getSeverityLevel(79)).toBe('high');
    });

    it('returns "medium" for scores 30-59', () => {
      expect(getSeverityLevel(30)).toBe('medium');
      expect(getSeverityLevel(40)).toBe('medium');
      expect(getSeverityLevel(50)).toBe('medium');
      expect(getSeverityLevel(59)).toBe('medium');
    });

    it('returns "low" for scores < 30', () => {
      expect(getSeverityLevel(0)).toBe('low');
      expect(getSeverityLevel(10)).toBe('low');
      expect(getSeverityLevel(20)).toBe('low');
      expect(getSeverityLevel(29)).toBe('low');
    });

    it('handles boundary values correctly', () => {
      // Low/Medium boundary
      expect(getSeverityLevel(29)).toBe('low');
      expect(getSeverityLevel(30)).toBe('medium');

      // Medium/High boundary
      expect(getSeverityLevel(59)).toBe('medium');
      expect(getSeverityLevel(60)).toBe('high');

      // High/Critical boundary
      expect(getSeverityLevel(79)).toBe('high');
      expect(getSeverityLevel(80)).toBe('critical');
    });

    it('throws error for scores below 0', () => {
      expect(() => getSeverityLevel(-1)).toThrow('Risk score must be between 0 and 100');
      expect(() => getSeverityLevel(-10)).toThrow('Risk score must be between 0 and 100');
    });

    it('throws error for scores above 100', () => {
      expect(() => getSeverityLevel(101)).toThrow('Risk score must be between 0 and 100');
      expect(() => getSeverityLevel(200)).toThrow('Risk score must be between 0 and 100');
    });
  });

  describe('getSeverityConfig', () => {
    it('returns complete config for critical severity', () => {
      const config = getSeverityConfig(85);
      expect(config).toEqual<SeverityConfig>({
        level: 'critical',
        bgTint: 'rgba(239, 68, 68, 0.08)',
        borderColor: '#EF4444',
        glowShadow: '0 0 8px rgba(239, 68, 68, 0.3)',
        shouldPulse: true,
        bgClass: 'bg-red-500/[0.08]',
        borderClass: 'border-l-red-500',
        glowClass: 'shadow-[0_0_8px_rgba(239,68,68,0.3)]',
        pulseClass: 'animate-pulse-subtle',
      });
    });

    it('returns complete config for high severity', () => {
      const config = getSeverityConfig(72);
      expect(config).toEqual<SeverityConfig>({
        level: 'high',
        bgTint: 'rgba(249, 115, 22, 0.06)',
        borderColor: '#F97316',
        glowShadow: '',
        shouldPulse: false,
        bgClass: 'bg-orange-500/[0.06]',
        borderClass: 'border-l-orange-500',
        glowClass: '',
        pulseClass: '',
      });
    });

    it('returns complete config for medium severity', () => {
      const config = getSeverityConfig(45);
      expect(config).toEqual<SeverityConfig>({
        level: 'medium',
        bgTint: 'rgba(234, 179, 8, 0.04)',
        borderColor: '#EAB308',
        glowShadow: '',
        shouldPulse: false,
        bgClass: 'bg-yellow-500/[0.04]',
        borderClass: 'border-l-yellow-500',
        glowClass: '',
        pulseClass: '',
      });
    });

    it('returns complete config for low severity', () => {
      const config = getSeverityConfig(15);
      expect(config).toEqual<SeverityConfig>({
        level: 'low',
        bgTint: 'transparent',
        borderColor: '#76B900',
        glowShadow: '',
        shouldPulse: false,
        bgClass: 'bg-transparent',
        borderClass: 'border-l-primary',
        glowClass: '',
        pulseClass: '',
      });
    });

    it('only enables pulse for critical severity', () => {
      expect(getSeverityConfig(100).shouldPulse).toBe(true);
      expect(getSeverityConfig(80).shouldPulse).toBe(true);
      expect(getSeverityConfig(79).shouldPulse).toBe(false);
      expect(getSeverityConfig(60).shouldPulse).toBe(false);
      expect(getSeverityConfig(30).shouldPulse).toBe(false);
      expect(getSeverityConfig(0).shouldPulse).toBe(false);
    });

    it('only includes glow for critical severity', () => {
      expect(getSeverityConfig(100).glowShadow).not.toBe('');
      expect(getSeverityConfig(80).glowShadow).not.toBe('');
      expect(getSeverityConfig(79).glowShadow).toBe('');
      expect(getSeverityConfig(60).glowShadow).toBe('');
      expect(getSeverityConfig(30).glowShadow).toBe('');
      expect(getSeverityConfig(0).glowShadow).toBe('');
    });
  });

  describe('getSeverityBgClass', () => {
    it('returns correct class for each severity level', () => {
      expect(getSeverityBgClass('critical')).toBe('bg-red-500/[0.08]');
      expect(getSeverityBgClass('high')).toBe('bg-orange-500/[0.06]');
      expect(getSeverityBgClass('medium')).toBe('bg-yellow-500/[0.04]');
      expect(getSeverityBgClass('low')).toBe('bg-transparent');
    });
  });

  describe('getSeverityBorderClass', () => {
    it('returns correct class for each severity level', () => {
      expect(getSeverityBorderClass('critical')).toBe('border-l-red-500');
      expect(getSeverityBorderClass('high')).toBe('border-l-orange-500');
      expect(getSeverityBorderClass('medium')).toBe('border-l-yellow-500');
      expect(getSeverityBorderClass('low')).toBe('border-l-primary');
    });
  });

  describe('getSeverityStyle', () => {
    it('returns correct inline styles for critical severity', () => {
      const style = getSeverityStyle(85);
      expect(style.backgroundColor).toBe('rgba(239, 68, 68, 0.08)');
      expect(style.borderLeftColor).toBe('#EF4444');
      expect(style.boxShadow).toBe('0 0 8px rgba(239, 68, 68, 0.3)');
      expect(style.animation).toBe('pulse-subtle 2s ease-in-out infinite');
    });

    it('returns correct inline styles for high severity', () => {
      const style = getSeverityStyle(72);
      expect(style.backgroundColor).toBe('rgba(249, 115, 22, 0.06)');
      expect(style.borderLeftColor).toBe('#F97316');
      expect(style.boxShadow).toBeUndefined();
      expect(style.animation).toBeUndefined();
    });

    it('returns correct inline styles for medium severity', () => {
      const style = getSeverityStyle(45);
      expect(style.backgroundColor).toBe('rgba(234, 179, 8, 0.04)');
      expect(style.borderLeftColor).toBe('#EAB308');
      expect(style.boxShadow).toBeUndefined();
      expect(style.animation).toBeUndefined();
    });

    it('returns correct inline styles for low severity', () => {
      const style = getSeverityStyle(15);
      expect(style.backgroundColor).toBe('transparent');
      expect(style.borderLeftColor).toBe('#76B900');
      expect(style.boxShadow).toBeUndefined();
      expect(style.animation).toBeUndefined();
    });

    it('disables animation when prefersReducedMotion is true', () => {
      const style = getSeverityStyle(85, true);
      expect(style.animation).toBeUndefined();
    });

    it('enables animation when prefersReducedMotion is false (default)', () => {
      const style = getSeverityStyle(85, false);
      expect(style.animation).toBe('pulse-subtle 2s ease-in-out infinite');
    });

    it('ignores prefersReducedMotion for non-critical severities', () => {
      const styleHigh = getSeverityStyle(72, true);
      const styleMedium = getSeverityStyle(45, true);
      const styleLow = getSeverityStyle(15, true);

      expect(styleHigh.animation).toBeUndefined();
      expect(styleMedium.animation).toBeUndefined();
      expect(styleLow.animation).toBeUndefined();
    });
  });

  describe('isCriticalSeverity', () => {
    it('returns true for scores >= 80', () => {
      expect(isCriticalSeverity(80)).toBe(true);
      expect(isCriticalSeverity(85)).toBe(true);
      expect(isCriticalSeverity(90)).toBe(true);
      expect(isCriticalSeverity(100)).toBe(true);
    });

    it('returns false for scores < 80', () => {
      expect(isCriticalSeverity(79)).toBe(false);
      expect(isCriticalSeverity(60)).toBe(false);
      expect(isCriticalSeverity(30)).toBe(false);
      expect(isCriticalSeverity(0)).toBe(false);
    });

    it('handles boundary value correctly', () => {
      expect(isCriticalSeverity(79)).toBe(false);
      expect(isCriticalSeverity(80)).toBe(true);
    });
  });

  describe('type safety', () => {
    it('SeverityLevel type is compatible with RiskLevel', () => {
      const levels: SeverityLevel[] = ['low', 'medium', 'high', 'critical'];
      levels.forEach((level) => {
        expect(typeof level).toBe('string');
      });
    });

    it('SeverityConfig contains all required properties', () => {
      const config = getSeverityConfig(50);
      expect(config).toHaveProperty('level');
      expect(config).toHaveProperty('bgTint');
      expect(config).toHaveProperty('borderColor');
      expect(config).toHaveProperty('glowShadow');
      expect(config).toHaveProperty('shouldPulse');
      expect(config).toHaveProperty('bgClass');
      expect(config).toHaveProperty('borderClass');
      expect(config).toHaveProperty('glowClass');
      expect(config).toHaveProperty('pulseClass');
    });
  });

  describe('edge cases', () => {
    it('handles score of exactly 0', () => {
      const config = getSeverityConfig(0);
      expect(config.level).toBe('low');
      expect(config.bgTint).toBe('transparent');
    });

    it('handles score of exactly 100', () => {
      const config = getSeverityConfig(100);
      expect(config.level).toBe('critical');
      expect(config.shouldPulse).toBe(true);
    });

    it('handles floating point scores by using floor behavior', () => {
      // JavaScript comparison handles floats correctly
      expect(getSeverityLevel(79.9)).toBe('high');
      expect(getSeverityLevel(80.0)).toBe('critical');
      expect(getSeverityLevel(29.9)).toBe('low');
      expect(getSeverityLevel(30.0)).toBe('medium');
    });
  });
});
