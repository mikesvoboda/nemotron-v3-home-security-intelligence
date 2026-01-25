/**
 * Tests for snooze utility functions
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  isSnoozed,
  getSnoozeRemainingMs,
  formatSnoozeEndTime,
  formatSnoozeRemaining,
  getSnoozeStatusMessage,
  SNOOZE_DURATIONS,
  SNOOZE_OPTIONS,
} from './snooze';

describe('snooze utilities', () => {
  const MOCK_NOW = new Date('2024-01-15T12:00:00Z');

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(MOCK_NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('SNOOZE_DURATIONS', () => {
    it('has correct duration values in milliseconds', () => {
      expect(SNOOZE_DURATIONS['15min']).toBe(15 * 60 * 1000);
      expect(SNOOZE_DURATIONS['1hour']).toBe(60 * 60 * 1000);
      expect(SNOOZE_DURATIONS['4hours']).toBe(4 * 60 * 60 * 1000);
      expect(SNOOZE_DURATIONS['24hours']).toBe(24 * 60 * 60 * 1000);
    });
  });

  describe('SNOOZE_OPTIONS', () => {
    it('has correct option values in seconds', () => {
      expect(SNOOZE_OPTIONS[0]).toEqual({ label: '15 minutes', value: 15 * 60 });
      expect(SNOOZE_OPTIONS[1]).toEqual({ label: '1 hour', value: 60 * 60 });
      expect(SNOOZE_OPTIONS[2]).toEqual({ label: '4 hours', value: 4 * 60 * 60 });
      expect(SNOOZE_OPTIONS[3]).toEqual({ label: '24 hours', value: 24 * 60 * 60 });
    });
  });

  describe('isSnoozed', () => {
    it('returns false for null snooze_until', () => {
      expect(isSnoozed(null)).toBe(false);
    });

    it('returns false for undefined snooze_until', () => {
      expect(isSnoozed(undefined)).toBe(false);
    });

    it('returns false for empty string snooze_until', () => {
      expect(isSnoozed('')).toBe(false);
    });

    it('returns true when snooze_until is in the future', () => {
      const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
      expect(isSnoozed(futureTime)).toBe(true);
    });

    it('returns false when snooze_until is in the past', () => {
      const pastTime = new Date(MOCK_NOW.getTime() - 60 * 60 * 1000).toISOString();
      expect(isSnoozed(pastTime)).toBe(false);
    });

    it('returns false when snooze_until is exactly now', () => {
      const exactlyNow = MOCK_NOW.toISOString();
      expect(isSnoozed(exactlyNow)).toBe(false);
    });

    it('returns false for invalid date string', () => {
      expect(isSnoozed('invalid-date')).toBe(false);
    });
  });

  describe('getSnoozeRemainingMs', () => {
    it('returns 0 for null snooze_until', () => {
      expect(getSnoozeRemainingMs(null)).toBe(0);
    });

    it('returns 0 for undefined snooze_until', () => {
      expect(getSnoozeRemainingMs(undefined)).toBe(0);
    });

    it('returns correct remaining time for future snooze_until', () => {
      const remainingMs = 30 * 60 * 1000; // 30 minutes
      const futureTime = new Date(MOCK_NOW.getTime() + remainingMs).toISOString();
      expect(getSnoozeRemainingMs(futureTime)).toBe(remainingMs);
    });

    it('returns 0 for past snooze_until', () => {
      const pastTime = new Date(MOCK_NOW.getTime() - 60 * 1000).toISOString();
      expect(getSnoozeRemainingMs(pastTime)).toBe(0);
    });

    it('returns 0 for invalid date string', () => {
      expect(getSnoozeRemainingMs('invalid-date')).toBe(0);
    });
  });

  describe('formatSnoozeEndTime', () => {
    it('returns empty string for null snooze_until', () => {
      expect(formatSnoozeEndTime(null)).toBe('');
    });

    it('returns empty string for undefined snooze_until', () => {
      expect(formatSnoozeEndTime(undefined)).toBe('');
    });

    it('returns formatted time for future snooze_until', () => {
      // Create a time 30 minutes in the future
      const futureTime = new Date(MOCK_NOW.getTime() + 30 * 60 * 1000);
      const result = formatSnoozeEndTime(futureTime.toISOString());

      // Result should be in format like "12:30 PM" (depends on locale)
      expect(result).toMatch(/\d{1,2}:\d{2}\s*(AM|PM)/);
    });

    it('returns empty string for past snooze_until', () => {
      const pastTime = new Date(MOCK_NOW.getTime() - 60 * 1000).toISOString();
      expect(formatSnoozeEndTime(pastTime)).toBe('');
    });

    it('returns empty string for invalid date string', () => {
      expect(formatSnoozeEndTime('invalid-date')).toBe('');
    });
  });

  describe('formatSnoozeRemaining', () => {
    it('returns empty string for null snooze_until', () => {
      expect(formatSnoozeRemaining(null)).toBe('');
    });

    it('returns empty string for undefined snooze_until', () => {
      expect(formatSnoozeRemaining(undefined)).toBe('');
    });

    it('returns hours and minutes for long durations', () => {
      // 1 hour 30 minutes from now
      const futureTime = new Date(MOCK_NOW.getTime() + 90 * 60 * 1000).toISOString();
      expect(formatSnoozeRemaining(futureTime)).toBe('1h 30m remaining');
    });

    it('returns hours only for exact hours', () => {
      // Exactly 2 hours from now
      const futureTime = new Date(MOCK_NOW.getTime() + 2 * 60 * 60 * 1000).toISOString();
      expect(formatSnoozeRemaining(futureTime)).toBe('2h remaining');
    });

    it('returns minutes for medium durations', () => {
      // 15 minutes from now
      const futureTime = new Date(MOCK_NOW.getTime() + 15 * 60 * 1000).toISOString();
      expect(formatSnoozeRemaining(futureTime)).toBe('15 min remaining');
    });

    it('returns less than 1 min for short durations', () => {
      // 30 seconds from now
      const futureTime = new Date(MOCK_NOW.getTime() + 30 * 1000).toISOString();
      expect(formatSnoozeRemaining(futureTime)).toBe('Less than 1 min remaining');
    });

    it('returns empty string for past snooze_until', () => {
      const pastTime = new Date(MOCK_NOW.getTime() - 60 * 1000).toISOString();
      expect(formatSnoozeRemaining(pastTime)).toBe('');
    });
  });

  describe('getSnoozeStatusMessage', () => {
    it('returns empty string for null snooze_until', () => {
      expect(getSnoozeStatusMessage(null)).toBe('');
    });

    it('returns empty string for undefined snooze_until', () => {
      expect(getSnoozeStatusMessage(undefined)).toBe('');
    });

    it('returns full status message for future snooze_until', () => {
      // 1 hour from now
      const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
      const result = getSnoozeStatusMessage(futureTime);

      // Should contain "Snoozed until" and time and remaining
      expect(result).toContain('Snoozed until');
      expect(result).toContain('remaining');
    });

    it('returns empty string for past snooze_until', () => {
      const pastTime = new Date(MOCK_NOW.getTime() - 60 * 1000).toISOString();
      expect(getSnoozeStatusMessage(pastTime)).toBe('');
    });
  });
});
