/**
 * Tests for Summary Type Guards
 *
 * @see NEM-2894
 */

import { describe, it, expect } from 'vitest';

import { isSummary, isSummaryUpdateMessage, Summary } from '../summary';

describe('isSummary type guard', () => {
  it('returns true for valid summary', () => {
    const summary: Summary = {
      id: 1,
      content: 'Test content',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    expect(isSummary(summary)).toBe(true);
  });

  it('returns true for summary with additional fields', () => {
    const summary = {
      id: 1,
      content: 'Test content',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
      extraField: 'ignored',
    };

    expect(isSummary(summary)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isSummary(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isSummary(undefined)).toBe(false);
  });

  it('returns false for primitive values', () => {
    expect(isSummary('string')).toBe(false);
    expect(isSummary(123)).toBe(false);
    expect(isSummary(true)).toBe(false);
  });

  it('returns false for empty object', () => {
    expect(isSummary({})).toBe(false);
  });

  it('returns false for object missing id', () => {
    const partial = {
      content: 'Test',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    expect(isSummary(partial)).toBe(false);
  });

  it('returns false for object missing content', () => {
    const partial = {
      id: 1,
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    expect(isSummary(partial)).toBe(false);
  });

  it('returns false for object missing eventCount', () => {
    const partial = {
      id: 1,
      content: 'Test',
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    expect(isSummary(partial)).toBe(false);
  });

  it('returns false for object missing windowStart', () => {
    const partial = {
      id: 1,
      content: 'Test',
      eventCount: 2,
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    expect(isSummary(partial)).toBe(false);
  });

  it('returns false for object missing windowEnd', () => {
    const partial = {
      id: 1,
      content: 'Test',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    expect(isSummary(partial)).toBe(false);
  });

  it('returns false for object missing generatedAt', () => {
    const partial = {
      id: 1,
      content: 'Test',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
    };

    expect(isSummary(partial)).toBe(false);
  });
});

describe('isSummaryUpdateMessage type guard', () => {
  it('returns true for valid message with null summaries', () => {
    const msg = {
      type: 'summary_update',
      data: { hourly: null, daily: null },
    };

    expect(isSummaryUpdateMessage(msg)).toBe(true);
  });

  it('returns true for valid message with summaries', () => {
    const msg = {
      type: 'summary_update',
      data: {
        hourly: {
          id: 1,
          content: 'Hourly summary',
          eventCount: 3,
          windowStart: '2026-01-18T14:00:00Z',
          windowEnd: '2026-01-18T15:00:00Z',
          generatedAt: '2026-01-18T14:55:00Z',
        },
        daily: {
          id: 2,
          content: 'Daily summary',
          eventCount: 10,
          windowStart: '2026-01-18T00:00:00Z',
          windowEnd: '2026-01-18T15:00:00Z',
          generatedAt: '2026-01-18T14:55:00Z',
        },
      },
    };

    expect(isSummaryUpdateMessage(msg)).toBe(true);
  });

  it('returns false for other message types', () => {
    const msg = { type: 'event_new', data: {} };

    expect(isSummaryUpdateMessage(msg)).toBe(false);
  });

  it('returns false for message without type', () => {
    const msg = { data: { hourly: null, daily: null } };

    expect(isSummaryUpdateMessage(msg)).toBe(false);
  });

  it('returns false for message without data', () => {
    const msg = { type: 'summary_update' };

    expect(isSummaryUpdateMessage(msg)).toBe(false);
  });

  it('returns false for null', () => {
    expect(isSummaryUpdateMessage(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isSummaryUpdateMessage(undefined)).toBe(false);
  });

  it('returns false for primitive values', () => {
    expect(isSummaryUpdateMessage('summary_update')).toBe(false);
    expect(isSummaryUpdateMessage(123)).toBe(false);
    expect(isSummaryUpdateMessage(true)).toBe(false);
  });

  it('returns false for empty object', () => {
    expect(isSummaryUpdateMessage({})).toBe(false);
  });

  it('returns false for wrong type value', () => {
    const msg = {
      type: 'event_update',
      data: { hourly: null, daily: null },
    };

    expect(isSummaryUpdateMessage(msg)).toBe(false);
  });
});
