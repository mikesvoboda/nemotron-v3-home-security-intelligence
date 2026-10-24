/**
 * Tests for the Trash purge-deadline mirror (F4.3).
 *
 * Each case pins a behaviour of backend/services/event_purger.py's
 * `purge_deadline_for_event` — if backend and frontend ever disagree, Trash
 * is showing a wrong purge date. Cases are named for the rule they pin.
 */

import { describe, it, expect } from 'vitest';

import {
  purgeDeadlineForEvent,
  formatPurgeDate,
  DEFAULT_TRASH_RETENTION_DAYS,
  TRASH_RETENTION_DISABLED,
} from '../trashPurge';

// Fixed instants, far from midnight so day-math stays unambiguous.
const DELETED_AT = new Date('2025-06-10T12:00:00Z');
const STARTED_AT = new Date('2025-06-01T12:00:00Z');

function expected(utcIso: string): Date {
  return new Date(utcIso);
}

describe('purgeDeadlineForEvent (mirrors event_purger.py purge_deadline_for_event)', () => {
  it('purges at deleted_at + trash_retention_days when the Trash clock is earlier', () => {
    // deleted + 30d = Jul 10; started + 365d = Jun 1 2026 → trash wins
    const deadline = purgeDeadlineForEvent(DELETED_AT, STARTED_AT, {
      retentionDays: 365,
      trashRetentionDays: 30,
    });
    expect(deadline).toEqual(expected('2025-07-10T12:00:00.000Z'));
  });

  it('purges at started_at + retention_days when general retention is earlier', () => {
    // started + 10d = Jun 11; deleted + 30d = Jul 10 → retention wins
    const deadline = purgeDeadlineForEvent(DELETED_AT, STARTED_AT, {
      retentionDays: 10,
      trashRetentionDays: 30,
    });
    expect(deadline).toEqual(expected('2025-06-11T12:00:00.000Z'));
  });

  it('treats equal deadlines as one deadline (min, not tie-break)', () => {
    // deleted + 9d = Jun 19; started + 18d = Jun 19 — same instant
    const deadline = purgeDeadlineForEvent(DELETED_AT, STARTED_AT, {
      retentionDays: 18,
      trashRetentionDays: 9,
    });
    expect(deadline).toEqual(expected('2025-06-19T12:00:00.000Z'));
  });

  it('with trash_retention_days = 0, only the general retention clock applies', () => {
    // Trash clock off: started + 30d = Jul 1, even though deleted + 5d is earlier
    const deadline = purgeDeadlineForEvent(DELETED_AT, STARTED_AT, {
      retentionDays: 30,
      trashRetentionDays: TRASH_RETENTION_DISABLED,
    });
    expect(deadline).toEqual(expected('2025-07-01T12:00:00.000Z'));
  });

  it('treats a negative trash_retention_days the same as 0 (clock off)', () => {
    const deadline = purgeDeadlineForEvent(DELETED_AT, STARTED_AT, {
      retentionDays: 30,
      trashRetentionDays: -3,
    });
    expect(deadline).toEqual(expected('2025-07-01T12:00:00.000Z'));
  });

  it('accepts ISO strings as well as Date objects', () => {
    const deadline = purgeDeadlineForEvent(DELETED_AT.toISOString(), STARTED_AT.toISOString(), {
      retentionDays: 365,
      trashRetentionDays: 30,
    });
    expect(deadline).toEqual(expected('2025-07-10T12:00:00.000Z'));
  });

  it('returns null on a malformed date string rather than inventing a deadline', () => {
    expect(
      purgeDeadlineForEvent('not-a-date', STARTED_AT, {
        retentionDays: 30,
        trashRetentionDays: 30,
      })
    ).toBeNull();
    expect(
      purgeDeadlineForEvent(DELETED_AT, 'also-not-a-date', {
        retentionDays: 30,
        trashRetentionDays: 30,
      })
    ).toBeNull();
  });

  it('returns null on malformed retention config instead of printing a false date', () => {
    // retention_days <= 0 is impossible per the backend schema (ge=1);
    // NaN/absent likewise. No clock → no printed date.
    expect(
      purgeDeadlineForEvent(DELETED_AT, STARTED_AT, { retentionDays: 0, trashRetentionDays: 30 })
    ).toBeNull();
    expect(
      purgeDeadlineForEvent(DELETED_AT, STARTED_AT, { retentionDays: -1, trashRetentionDays: 30 })
    ).toBeNull();
    expect(
      purgeDeadlineForEvent(DELETED_AT, STARTED_AT, { retentionDays: NaN, trashRetentionDays: 30 })
    ).toBeNull();
  });

  it('exports the backend-default trash retention (30) for pre-B4.4 backends', () => {
    expect(DEFAULT_TRASH_RETENTION_DAYS).toBe(30);
  });
});

describe('formatPurgeDate', () => {
  it('renders a deadline as a calendar date', () => {
    // Format with an explicit en-US locale and UTC to keep the assertion
    // timezone-stable: the formatter uses the runtime locale, the test pins
    // the input date at noon UTC so any reasonable TZ offset lands the same day.
    expect(formatPurgeDate(new Date('2025-07-10T12:00:00Z'))).toMatch(/Jul 10, 2025/);
  });

  it('states when no clock applies', () => {
    expect(formatPurgeDate(null)).toBe('No purge scheduled');
  });
});
