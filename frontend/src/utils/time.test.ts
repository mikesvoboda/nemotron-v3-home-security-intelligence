import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { formatDuration, getDurationLabel, isEventOngoing } from './time';

describe('time utilities', () => {
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('formatDuration', () => {
    it('formats duration under a minute with seconds only', () => {
      const start = new Date(BASE_TIME - 30 * 1000).toISOString(); // 30 seconds ago
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('30s');
    });

    it('formats duration of exactly 1 minute', () => {
      const start = new Date(BASE_TIME - 60 * 1000).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('1m');
    });

    it('formats duration with minutes and seconds', () => {
      const start = new Date(BASE_TIME - 150 * 1000).toISOString(); // 2 minutes 30 seconds
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('2m 30s');
    });

    it('formats duration with only minutes (no remaining seconds)', () => {
      const start = new Date(BASE_TIME - 5 * 60 * 1000).toISOString(); // 5 minutes
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('5m');
    });

    it('formats duration with hours and minutes', () => {
      const start = new Date(BASE_TIME - 90 * 60 * 1000).toISOString(); // 1 hour 30 minutes
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('1h 30m');
    });

    it('formats duration with only hours (no remaining minutes)', () => {
      const start = new Date(BASE_TIME - 2 * 60 * 60 * 1000).toISOString(); // 2 hours
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('2h');
    });

    it('formats duration with days and hours', () => {
      const start = new Date(BASE_TIME - 36 * 60 * 60 * 1000).toISOString(); // 1 day 12 hours
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('1d 12h');
    });

    it('formats duration with only days (no remaining hours)', () => {
      const start = new Date(BASE_TIME - 3 * 24 * 60 * 60 * 1000).toISOString(); // 3 days
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('3d');
    });

    it('formats very short duration (0 seconds)', () => {
      const start = new Date(BASE_TIME).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('0s');
    });

    it('formats very short duration (less than 1 second)', () => {
      const start = new Date(BASE_TIME - 500).toISOString(); // 500ms
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('0s');
    });

    it('handles negative duration gracefully', () => {
      const start = new Date(BASE_TIME + 1000).toISOString(); // 1 second in future
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('0s');
    });

    it('returns "ongoing" for recent events without ended_at', () => {
      const start = new Date(BASE_TIME - 2 * 60 * 1000).toISOString(); // 2 minutes ago
      expect(formatDuration(start, null)).toBe('ongoing');
    });

    it('returns duration with "(ongoing)" suffix for older ongoing events', () => {
      const start = new Date(BASE_TIME - 10 * 60 * 1000).toISOString(); // 10 minutes ago
      const result = formatDuration(start, null);
      expect(result).toContain('(ongoing)');
      expect(result).toContain('10m');
    });

    it('returns duration with "(ongoing)" suffix for very old ongoing events', () => {
      const start = new Date(BASE_TIME - 2 * 60 * 60 * 1000).toISOString(); // 2 hours ago
      const result = formatDuration(start, null);
      expect(result).toContain('(ongoing)');
      expect(result).toContain('2h');
    });

    it('handles invalid start timestamp', () => {
      expect(formatDuration('invalid-date', new Date(BASE_TIME).toISOString())).toBe('unknown');
    });

    it('handles invalid end timestamp', () => {
      expect(formatDuration(new Date(BASE_TIME).toISOString(), 'invalid-date')).toBe('unknown');
    });

    it('handles both invalid timestamps', () => {
      expect(formatDuration('invalid-date', 'invalid-date')).toBe('unknown');
    });

    it('formats complex duration with hours, minutes, and seconds', () => {
      const start = new Date(BASE_TIME - (2 * 60 * 60 + 15 * 60 + 45) * 1000).toISOString(); // 2h 15m 45s
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('2h 15m');
    });

    it('formats duration at exactly 1 hour boundary', () => {
      const start = new Date(BASE_TIME - 60 * 60 * 1000).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('1h');
    });

    it('formats duration at exactly 1 day boundary', () => {
      const start = new Date(BASE_TIME - 24 * 60 * 60 * 1000).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('1d');
    });

    it('formats 59 seconds as 59s', () => {
      const start = new Date(BASE_TIME - 59 * 1000).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('59s');
    });

    it('formats 59 minutes 59 seconds as 59m 59s', () => {
      const start = new Date(BASE_TIME - (59 * 60 + 59) * 1000).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('59m 59s');
    });

    it('formats 23 hours 59 minutes as 23h 59m', () => {
      const start = new Date(BASE_TIME - (23 * 60 * 60 + 59 * 60) * 1000).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('23h 59m');
    });
  });

  describe('getDurationLabel', () => {
    it('returns formatted duration for completed events', () => {
      const start = new Date(BASE_TIME - 150 * 1000).toISOString();
      const end = new Date(BASE_TIME).toISOString();
      expect(getDurationLabel(start, end)).toBe('2m 30s');
    });

    it('returns "ongoing" for recent ongoing events', () => {
      const start = new Date(BASE_TIME - 2 * 60 * 1000).toISOString();
      expect(getDurationLabel(start, null)).toBe('ongoing');
    });

    it('returns duration with "(ongoing)" for older ongoing events', () => {
      const start = new Date(BASE_TIME - 10 * 60 * 1000).toISOString();
      const result = getDurationLabel(start, null);
      expect(result).toContain('(ongoing)');
    });
  });

  describe('isEventOngoing', () => {
    it('returns true when endedAt is null', () => {
      expect(isEventOngoing(null)).toBe(true);
    });

    it('returns false when endedAt is a valid timestamp', () => {
      const end = new Date(BASE_TIME).toISOString();
      expect(isEventOngoing(end)).toBe(false);
    });

    it('returns false when endedAt is any non-null string', () => {
      expect(isEventOngoing('2024-01-15T10:00:00Z')).toBe(false);
    });
  });

  describe('edge cases', () => {
    it('handles very large durations (weeks)', () => {
      const start = new Date(BASE_TIME - 14 * 24 * 60 * 60 * 1000).toISOString(); // 14 days
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('14d');
    });

    it('handles leap year day duration', () => {
      const start = new Date(BASE_TIME - 366 * 24 * 60 * 60 * 1000).toISOString(); // 366 days
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('366d');
    });

    it('handles millisecond precision', () => {
      const start = new Date(BASE_TIME - 1234).toISOString(); // 1.234 seconds
      const end = new Date(BASE_TIME).toISOString();
      expect(formatDuration(start, end)).toBe('1s');
    });

    it('handles ongoing event at exactly 5 minute boundary', () => {
      const start = new Date(BASE_TIME - 5 * 60 * 1000).toISOString();
      const result = formatDuration(start, null);
      expect(result).toContain('(ongoing)');
    });

    it('handles ongoing event just under 5 minute boundary', () => {
      const start = new Date(BASE_TIME - 4 * 60 * 1000 - 59 * 1000).toISOString(); // 4m 59s
      expect(formatDuration(start, null)).toBe('ongoing');
    });

    it('handles ongoing event just over 5 minute boundary', () => {
      const start = new Date(BASE_TIME - 5 * 60 * 1000 - 1000).toISOString(); // 5m 1s
      const result = formatDuration(start, null);
      expect(result).toContain('(ongoing)');
    });
  });
});
