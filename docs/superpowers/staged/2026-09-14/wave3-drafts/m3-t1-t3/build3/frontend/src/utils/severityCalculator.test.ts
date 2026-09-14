/**
 * Tests for Severity Calculator
 *
 * @see NEM-2924
 */

import { describe, it, expect } from 'vitest';

import {
  calculateSeverity,
  getSeverityConfig,
  shouldShowCriticalAnimation,
  type SeverityInput,
  type SeverityLevel,
} from './severityCalculator';

describe('severityCalculator', () => {
  describe('calculateSeverity', () => {
    describe('priority 1: maxRiskScore', () => {
      it('returns critical for maxRiskScore >= 80', () => {
        const input: SeverityInput = {
          content: 'Some routine content',
          eventCount: 1,
          maxRiskScore: 80,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('critical');
        expect(result.label).toBe('Critical');
        expect(result.color).toBe('red');
      });

      it('returns critical for maxRiskScore = 100', () => {
        const input: SeverityInput = {
          content: 'Normal activity',
          eventCount: 1,
          maxRiskScore: 100,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('critical');
      });

      it('returns high for maxRiskScore >= 60 and < 80', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 60,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('high');
        expect(result.label).toBe('High activity');
        expect(result.color).toBe('orange');
      });

      it('returns high for maxRiskScore = 79', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 79,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('high');
      });

      it('returns medium for maxRiskScore >= 40 and < 60', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 40,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('medium');
        expect(result.label).toBe('Moderate activity');
        expect(result.color).toBe('yellow');
      });

      it('returns medium for maxRiskScore = 59', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 59,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('medium');
      });

      it('returns low for maxRiskScore >= 20 and < 40', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 20,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('low');
        expect(result.label).toBe('Low activity');
        expect(result.color).toBe('green');
      });

      it('returns low for maxRiskScore = 39', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 39,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('low');
      });

      it('returns clear for maxRiskScore < 20', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 19,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('clear');
        expect(result.label).toBe('All clear');
        expect(result.color).toBe('emerald');
      });

      it('returns clear for maxRiskScore = 0', () => {
        const input: SeverityInput = {
          content: 'Some content',
          eventCount: 1,
          maxRiskScore: 0,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('clear');
      });

      it('maxRiskScore takes precedence over keywords', () => {
        // Content has critical keyword but low risk score
        const input: SeverityInput = {
          content: 'Critical alert: false alarm test',
          eventCount: 1,
          maxRiskScore: 15,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('clear');
      });

      it('maxRiskScore takes precedence over event count', () => {
        const input: SeverityInput = {
          content: 'Some activity',
          eventCount: 100,
          maxRiskScore: 10,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('clear');
      });
    });

    describe('priority 2: keyword detection (when no maxRiskScore)', () => {
      describe('critical keywords', () => {
        it.each([
          ['critical', 'Critical alert detected'],
          ['emergency', 'Emergency response required'],
          ['intruder', 'Intruder detected in backyard'],
          ['breach', 'Security breach at front door'],
          ['weapon', 'Weapon detected by AI'],
          ['threat', 'Active threat identified'],
        ])('detects "%s" keyword', (_keyword, content) => {
          const input: SeverityInput = { content, eventCount: 1 };
          const result = calculateSeverity(input);
          expect(result.level).toBe('critical');
          expect(result.color).toBe('red');
        });

        it('is case-insensitive for critical keywords', () => {
          const input: SeverityInput = {
            content: 'CRITICAL EMERGENCY detected',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('critical');
        });
      });

      describe('high keywords', () => {
        it.each([
          ['high-risk', 'High-risk behavior observed'],
          ['suspicious', 'Suspicious activity at gate'],
          ['masked', 'Masked individual detected'],
          ['obscured face', 'Person with obscured face seen'],
          ['loitering', 'Someone loitering near entrance'],
          ['trespassing', 'Trespassing detected on property'],
        ])('detects "%s" keyword', (_keyword, content) => {
          const input: SeverityInput = { content, eventCount: 1 };
          const result = calculateSeverity(input);
          expect(result.level).toBe('high');
          expect(result.color).toBe('orange');
        });

        it('is case-insensitive for high keywords', () => {
          const input: SeverityInput = {
            content: 'SUSPICIOUS LOITERING detected',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('high');
        });
      });

      describe('medium keywords', () => {
        it.each([
          ['unusual', 'Unusual activity in garage'],
          ['unexpected', 'Unexpected visitor at door'],
          ['unfamiliar', 'Unfamiliar vehicle in driveway'],
          ['monitoring', 'Monitoring ongoing situation'],
        ])('detects "%s" keyword', (_keyword, content) => {
          const input: SeverityInput = { content, eventCount: 1 };
          const result = calculateSeverity(input);
          expect(result.level).toBe('medium');
          expect(result.color).toBe('yellow');
        });

        it('is case-insensitive for medium keywords', () => {
          const input: SeverityInput = {
            content: 'UNUSUAL UNEXPECTED activity',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('medium');
        });
      });

      describe('low keywords', () => {
        it.each([
          ['routine', 'Routine patrol detected'],
          ['normal', 'Normal activity observed'],
          ['expected', 'Expected visitor arrived'],
          ['delivery', 'Package delivery completed'],
        ])('detects "%s" keyword', (_keyword, content) => {
          const input: SeverityInput = { content, eventCount: 1 };
          const result = calculateSeverity(input);
          expect(result.level).toBe('low');
          expect(result.color).toBe('green');
        });

        it('is case-insensitive for low keywords', () => {
          const input: SeverityInput = {
            content: 'ROUTINE DELIVERY completed',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('low');
        });
      });

      describe('keyword priority', () => {
        it('critical takes precedence over high', () => {
          const input: SeverityInput = {
            content: 'Suspicious intruder detected',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('critical');
        });

        it('critical takes precedence over medium', () => {
          const input: SeverityInput = {
            content: 'Unusual critical situation',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('critical');
        });

        it('critical takes precedence over low', () => {
          const input: SeverityInput = {
            content: 'Routine emergency drill',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('critical');
        });

        it('high takes precedence over medium', () => {
          const input: SeverityInput = {
            content: 'Unusual suspicious activity',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('high');
        });

        it('high takes precedence over low', () => {
          const input: SeverityInput = {
            content: 'Normal loitering behavior',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('high');
        });

        it('medium takes precedence over low', () => {
          const input: SeverityInput = {
            content: 'Routine but unusual activity',
            eventCount: 1,
          };
          const result = calculateSeverity(input);
          expect(result.level).toBe('medium');
        });
      });
    });

    describe('priority 3: event count fallback', () => {
      it('returns low when events exist but no keywords match', () => {
        const input: SeverityInput = {
          content: 'Activity recorded in the area',
          eventCount: 5,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('low');
      });

      it('returns clear when no events and no keywords', () => {
        const input: SeverityInput = {
          content: 'No significant activity',
          eventCount: 0,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('clear');
      });

      it('returns clear for empty content and no events', () => {
        const input: SeverityInput = {
          content: '',
          eventCount: 0,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('clear');
      });
    });

    describe('edge cases', () => {
      it('handles undefined maxRiskScore', () => {
        const input: SeverityInput = {
          content: 'Critical alert',
          eventCount: 1,
          maxRiskScore: undefined,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('critical');
      });

      it('ignores invalid maxRiskScore > 100', () => {
        const input: SeverityInput = {
          content: 'Critical alert',
          eventCount: 1,
          maxRiskScore: 150,
        };
        // Falls back to keyword detection
        const result = calculateSeverity(input);
        expect(result.level).toBe('critical');
      });

      it('ignores invalid maxRiskScore < 0', () => {
        const input: SeverityInput = {
          content: 'Critical alert',
          eventCount: 1,
          maxRiskScore: -10,
        };
        // Falls back to keyword detection
        const result = calculateSeverity(input);
        expect(result.level).toBe('critical');
      });

      it('handles special characters in content', () => {
        const input: SeverityInput = {
          content: '!!!CRITICAL!!! alert @#$%',
          eventCount: 1,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('critical');
      });

      it('handles multi-line content', () => {
        const input: SeverityInput = {
          content: 'First line\nSecond line with intruder\nThird line',
          eventCount: 1,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('critical');
      });

      it('handles keyword at word boundary', () => {
        const input: SeverityInput = {
          content: 'Suspicious-looking person',
          eventCount: 1,
        };
        const result = calculateSeverity(input);
        expect(result.level).toBe('high');
      });
    });

    describe('result properties', () => {
      it('returns complete SeverityResult for critical', () => {
        const input: SeverityInput = {
          content: 'Critical alert',
          eventCount: 1,
        };
        const result = calculateSeverity(input);
        expect(result).toEqual({
          level: 'critical',
          label: 'Critical',
          color: 'red',
          borderColor: '#ef4444',
        });
      });

      it('returns complete SeverityResult for high', () => {
        const input: SeverityInput = {
          content: 'Suspicious activity',
          eventCount: 1,
        };
        const result = calculateSeverity(input);
        expect(result).toEqual({
          level: 'high',
          label: 'High activity',
          color: 'orange',
          borderColor: '#f97316',
        });
      });

      it('returns complete SeverityResult for medium', () => {
        const input: SeverityInput = {
          content: 'Unusual activity',
          eventCount: 1,
        };
        const result = calculateSeverity(input);
        expect(result).toEqual({
          level: 'medium',
          label: 'Moderate activity',
          color: 'yellow',
          borderColor: '#eab308',
        });
      });

      it('returns complete SeverityResult for low', () => {
        const input: SeverityInput = {
          content: 'Routine activity',
          eventCount: 1,
        };
        const result = calculateSeverity(input);
        expect(result).toEqual({
          level: 'low',
          label: 'Low activity',
          color: 'green',
          borderColor: '#22c55e',
        });
      });

      it('returns complete SeverityResult for clear', () => {
        const input: SeverityInput = {
          content: 'Nothing happened',
          eventCount: 0,
        };
        const result = calculateSeverity(input);
        expect(result).toEqual({
          level: 'clear',
          label: 'All clear',
          color: 'emerald',
          borderColor: '#10b981',
        });
      });
    });
  });

  describe('getSeverityConfig', () => {
    it.each<[SeverityLevel, string, string]>([
      ['clear', 'All clear', 'emerald'],
      ['low', 'Low activity', 'green'],
      ['medium', 'Moderate activity', 'yellow'],
      ['high', 'High activity', 'orange'],
      ['critical', 'Critical', 'red'],
    ])('returns correct config for %s level', (level, expectedLabel, expectedColor) => {
      const config = getSeverityConfig(level);
      expect(config.level).toBe(level);
      expect(config.label).toBe(expectedLabel);
      expect(config.color).toBe(expectedColor);
    });
  });

  describe('shouldShowCriticalAnimation', () => {
    it('returns true for critical level', () => {
      expect(shouldShowCriticalAnimation('critical')).toBe(true);
    });

    it('returns false for high level', () => {
      expect(shouldShowCriticalAnimation('high')).toBe(false);
    });

    it('returns false for medium level', () => {
      expect(shouldShowCriticalAnimation('medium')).toBe(false);
    });

    it('returns false for low level', () => {
      expect(shouldShowCriticalAnimation('low')).toBe(false);
    });

    it('returns false for clear level', () => {
      expect(shouldShowCriticalAnimation('clear')).toBe(false);
    });
  });
});
