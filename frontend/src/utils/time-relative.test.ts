import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  formatDuration,
  formatRelativeTime,
  formatSecondsAsHumanReadable,
  isTimestampStale,
} from './time';

/**
 * FE mutation batch 1 (WP4.3 frontend depth): every assertion below pins the
 * MEASURED shipped output of the three previously-untested time.ts exports
 * (probe-measured 2026-09-22 against this source — values are outputs, never
 * assumed). The shipped time.test.ts only exercises formatDuration /
 * getDurationLabel / isEventOngoing, which is exactly where the stryker
 * baseline's 57 time.ts survivors concentrated: formatRelativeTime boundary
 * chain, isTimestampStale, formatSecondsAsHumanReadable plural cascade.
 * Production is not bent to any mutant; fixtures match observed behavior.
 */
describe('formatRelativeTime', () => {
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const ago = (seconds: number) => new Date(BASE_TIME - seconds * 1000).toISOString();

  it('returns "Never" for null', () => {
    expect(formatRelativeTime(null)).toBe('Never');
  });

  it('returns "Invalid date" for an unparseable timestamp', () => {
    expect(formatRelativeTime('not-a-timestamp')).toBe('Invalid date');
  });

  it('uses "Just now" for the sub-minute band including zero, and for future timestamps', () => {
    // Measured: negative diffs (future date) also fall in this band —
    // Math.floor(-30/60)... the guard is diffSeconds < 60, and -30 < 60.
    expect(formatRelativeTime(ago(0))).toBe('Just now');
    expect(formatRelativeTime(ago(30))).toBe('Just now');
    expect(formatRelativeTime(ago(59))).toBe('Just now');
    expect(formatRelativeTime(ago(-30))).toBe('Just now');
    expect(formatRelativeTime(ago(-120))).toBe('Just now');
  });

  it('flips out of "Just now" at exactly 60 seconds', () => {
    expect(formatRelativeTime(ago(60))).toBe('1 minute ago');
  });

  it('formats the minutes band with singular/plural forms', () => {
    expect(formatRelativeTime(ago(119))).toBe('1 minute ago');
    expect(formatRelativeTime(ago(120))).toBe('2 minutes ago');
    expect(formatRelativeTime(ago(3599))).toBe('59 minutes ago');
  });

  it('flips to hours at exactly 3600 seconds and formats the hours band', () => {
    expect(formatRelativeTime(ago(3600))).toBe('1 hour ago');
    expect(formatRelativeTime(ago(7199))).toBe('1 hour ago');
    expect(formatRelativeTime(ago(86399))).toBe('23 hours ago');
  });

  it('flips to days at exactly 86400 seconds and formats the days band', () => {
    expect(formatRelativeTime(ago(86400))).toBe('1 day ago');
    expect(formatRelativeTime(ago(172800))).toBe('2 days ago');
    expect(formatRelativeTime(ago(2591999))).toBe('29 days ago');
  });

  it('switches to the absolute date at exactly 30 days', () => {
    // Locale-independent: compare against the same toLocaleDateString the
    // shipped code produces for the same Date.
    const d = new Date(BASE_TIME - 2592000 * 1000);
    expect(formatRelativeTime(d.toISOString())).toBe(d.toLocaleDateString());
    // And just below the boundary it is still relative — kills the
    // `< 30` → false mutant that would absolutize recent dates.
    expect(formatRelativeTime(ago(172799))).toBe('1 day ago');
  });

  it('returns "Invalid date" when coercion of the timestamp throws (catch block)', () => {
    // fe1b: kills time.ts:154 "'Invalid date'" -> "" (NoCoverage survivor).
    // Probe-measured: new Date(obj) coerces via Symbol.toPrimitive; the
    // shipped catch returns 'Invalid date' (never thrown to the caller).
    const throwing = {
      [Symbol.toPrimitive]: () => {
        throw new Error('forced');
      },
    };
    expect(formatRelativeTime(throwing as unknown as string)).toBe('Invalid date');
  });
});

describe('isTimestampStale', () => {
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const ago = (seconds: number) => new Date(BASE_TIME - seconds * 1000).toISOString();

  it('treats null and unparseable timestamps as stale', () => {
    expect(isTimestampStale(null)).toBe(true);
    expect(isTimestampStale('not-a-timestamp')).toBe(true);
  });

  it('is not stale strictly below the default 24h threshold, including exactly 24h', () => {
    // Measured boundary: 24h exactly is NOT stale (strict >); 24h+1s is.
    expect(isTimestampStale(ago(23 * 3600))).toBe(false);
    expect(isTimestampStale(ago(24 * 3600))).toBe(false);
    expect(isTimestampStale(ago(24 * 3600 + 1))).toBe(true);
  });

  it('honors a custom staleAfterHours with the same strict-> boundary', () => {
    expect(isTimestampStale(ago(12 * 3600), 12)).toBe(false);
    expect(isTimestampStale(ago(13 * 3600), 12)).toBe(true);
  });

  it('is not stale for future timestamps', () => {
    expect(isTimestampStale(ago(-3600))).toBe(false);
  });

  it('is stale when coercion of the timestamp throws (catch block)', () => {
    // fe1b: kills time.ts:182 `true` -> `false` (NoCoverage survivor).
    // Probe-measured: shipped catch returns true (fail-safe stale).
    const throwing = {
      [Symbol.toPrimitive]: () => {
        throw new Error('forced');
      },
    };
    expect(isTimestampStale(throwing as unknown as string)).toBe(true);
  });
});

describe('formatSecondsAsHumanReadable', () => {
  it('formats the seconds band with singular/plural forms', () => {
    expect(formatSecondsAsHumanReadable(0)).toBe('0 seconds');
    expect(formatSecondsAsHumanReadable(1)).toBe('1 second');
    expect(formatSecondsAsHumanReadable(59)).toBe('59 seconds');
  });

  it('flips to minutes at 60 and keeps the minutes-only path under an hour', () => {
    expect(formatSecondsAsHumanReadable(60)).toBe('1 minute');
    expect(formatSecondsAsHumanReadable(61)).toBe('1 minute');
    expect(formatSecondsAsHumanReadable(119)).toBe('1 minute');
    expect(formatSecondsAsHumanReadable(120)).toBe('2 minutes');
    expect(formatSecondsAsHumanReadable(3599)).toBe('59 minutes');
  });

  it('formats the hours band, dropping zero remaining minutes', () => {
    expect(formatSecondsAsHumanReadable(3600)).toBe('1 hour');
    expect(formatSecondsAsHumanReadable(3660)).toBe('1 hour 1 minute');
    expect(formatSecondsAsHumanReadable(7199)).toBe('1 hour 59 minutes');
    expect(formatSecondsAsHumanReadable(7200)).toBe('2 hours');
    expect(formatSecondsAsHumanReadable(7260)).toBe('2 hours 1 minute');
    expect(formatSecondsAsHumanReadable(86399)).toBe('23 hours 59 minutes');
  });

  it('formats the days band, dropping zero remaining hours', () => {
    expect(formatSecondsAsHumanReadable(86400)).toBe('1 day');
    expect(formatSecondsAsHumanReadable(90000)).toBe('1 day 1 hour');
    expect(formatSecondsAsHumanReadable(90061)).toBe('1 day 1 hour');
    expect(formatSecondsAsHumanReadable(172800)).toBe('2 days');
  });

  it('formats plural days with plural hours (fe1b gap combos)', () => {
    // fe1b: probe-measured on HEAD source. The battery's earlier pins only
    // entered the days+hours branch with days===1 (kills 340/344 need
    // days!==1) or remainingHours===1 (kills 345/349 need remainingHours
    // !==1) — these four combos make every template reachable.
    expect(formatSecondsAsHumanReadable(176400)).toBe('2 days 1 hour'); // 340+344 die
    expect(formatSecondsAsHumanReadable(180000)).toBe('2 days 2 hours'); // 345+349 die
    expect(formatSecondsAsHumanReadable(262800)).toBe('3 days 1 hour');
  });
});

describe('formatDuration (fe1b survivors)', () => {
  it('returns "unknown" when coercion of the start timestamp throws (catch block)', () => {
    // fe1b: kills time.ts:44 "'unknown'" -> "" (NoCoverage survivor id=188).
    // Probe-measured /tmp/fe1c-probe.json: shipped catch returns 'unknown'.
    const throwing = {
      [Symbol.toPrimitive]: () => {
        throw new Error('forced');
      },
    };
    expect(formatDuration(throwing as unknown as string, null)).toBe('unknown');
  });

  // fe1b per-mutant EQUIVALENT proof (id=169, time.ts:25 `durationMs < 0`
  // -> `durationMs <= 0`): measured on HEAD — formatDuration(t, t) with a
  // ZERO duration already returns '0s' (the value formatDurationValue(0)
  // produces), and negative input returns '0s' too. The mutant only
  // changes the branch taken at durationMs === 0, and both branches
  // return the identical string '0s'. No input distinguishes the pair.
});
