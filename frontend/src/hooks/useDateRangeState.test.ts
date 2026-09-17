/**
 * Tests for useDateRangeState (WP0.6 CI-truth follow-up).
 *
 * Surfaced by PR #6549: the WP0.1-repaired coverage gate (first run in which
 * get_changed_files actually parsed anything) reported this hook
 * MISSING TESTS — the hook shipped on main while the gate's parser was
 * congenitally blind. These tests align coverage to the SHIPPED contract
 * (URL-param persistence, preset math in UTC, custom-range validation).
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { calculatePresetRange, PRESET_LABELS, useDateRangeState } from './useDateRangeState';

import type { DateRangePreset } from './useDateRangeState';

// Controllable URL state: the hook reads params and writes via setSearchParams.
let initialParams = new URLSearchParams();
const setSearchParams = vi.fn((updater: (prev: URLSearchParams) => URLSearchParams) => {
  if (typeof updater === 'function') {
    initialParams = updater(initialParams);
  }
});

vi.mock('react-router-dom', () => ({
  useSearchParams: () => [initialParams, setSearchParams],
}));

beforeEach(() => {
  initialParams = new URLSearchParams();
  setSearchParams.mockClear();
});

describe('useDateRangeState', () => {
  it('defaults to the 7d preset with no URL param', () => {
    const { result } = renderHook(() => useDateRangeState());
    expect(result.current.preset).toBe('7d');
    expect(result.current.isCustom).toBe(false);
    expect(result.current.presetLabel).toBe('Last 7 days');
  });

  it('honours defaultPreset when nothing is in the URL', () => {
    const { result } = renderHook(() => useDateRangeState({ defaultPreset: '24h' }));
    expect(result.current.preset).toBe('24h');
  });

  it('reads a valid preset from the URL param', () => {
    initialParams = new URLSearchParams({ range: '30d' });
    const { result } = renderHook(() => useDateRangeState());
    expect(result.current.preset).toBe('30d');
  });

  it('falls back to the default for a garbage preset param', () => {
    initialParams = new URLSearchParams({ range: 'nonsense' });
    const { result } = renderHook(() => useDateRangeState());
    expect(result.current.preset).toBe('7d');
  });

  it('setPreset writes the param and clears custom start/end', () => {
    initialParams = new URLSearchParams({
      range: 'custom',
      start: '2026-01-01',
      end: '2026-01-31',
    });
    const { result } = renderHook(() => useDateRangeState());

    act(() => result.current.setPreset('90d'));

    expect(initialParams.get('range')).toBe('90d');
    expect(initialParams.has('start')).toBe(false);
    expect(initialParams.has('end')).toBe(false);
  });

  it('setPreset("custom") is a no-op — custom needs dates', () => {
    const { result } = renderHook(() => useDateRangeState());
    act(() => result.current.setPreset('custom'));
    expect(initialParams.has('range')).toBe(false);
  });

  it('setCustomRange writes custom + UTC-formatted start/end', () => {
    const { result } = renderHook(() => useDateRangeState());
    act(() =>
      result.current.setCustomRange(
        new Date('2026-03-01T12:00:00Z'),
        new Date('2026-03-15T12:00:00Z')
      )
    );
    expect(initialParams.get('range')).toBe('custom');
    expect(initialParams.get('start')).toBe('2026-03-01');
    expect(initialParams.get('end')).toBe('2026-03-15');
  });

  it('a valid custom range in the URL round-trips through range/apiParams', () => {
    initialParams = new URLSearchParams({
      range: 'custom',
      start: '2026-02-01',
      end: '2026-02-28',
    });
    const { result } = renderHook(() => useDateRangeState());

    expect(result.current.preset).toBe('custom');
    expect(result.current.isCustom).toBe(true);
    expect(result.current.apiParams).toEqual({
      start_date: '2026-02-01',
      end_date: '2026-02-28',
    });
    // End is pinned to end-of-day UTC (shipped contract).
    expect(result.current.range.endDate.toISOString()).toBe('2026-02-28T23:59:59.999Z');
  });

  it('custom preset with missing/invalid dates falls back to defaultPreset', () => {
    initialParams = new URLSearchParams({ range: 'custom', start: 'not-a-date' });
    const { result } = renderHook(() => useDateRangeState({ defaultPreset: 'today' }));
    expect(result.current.preset).toBe('today');
  });

  it("'all' emits empty api params (no date filter)", () => {
    initialParams = new URLSearchParams({ range: 'all' });
    const { result } = renderHook(() => useDateRangeState());
    expect(result.current.apiParams).toEqual({ start_date: '', end_date: '' });
  });

  it('reset() clears the range params back to default', () => {
    initialParams = new URLSearchParams({ range: '30d' });
    const { result } = renderHook(() => useDateRangeState());
    act(() => result.current.reset());
    expect(initialParams.has('range')).toBe(false);
  });

  it('reset() also clears a custom range with its start/end', () => {
    initialParams = new URLSearchParams({
      range: 'custom',
      start: '2026-01-01',
      end: '2026-01-15',
    });
    const { result } = renderHook(() => useDateRangeState());
    act(() => result.current.reset());
    expect(initialParams.has('range')).toBe(false);
    expect(initialParams.has('start')).toBe(false);
    expect(initialParams.has('end')).toBe(false);
  });

  it('a preset range emits YYYY-MM-DD apiParams', () => {
    initialParams = new URLSearchParams({ range: '7d' });
    const { result } = renderHook(() => useDateRangeState());
    expect(result.current.apiParams.start_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(result.current.apiParams.end_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('an empty range= param falls back to the default', () => {
    initialParams = new URLSearchParams({ range: '' });
    const { result } = renderHook(() => useDateRangeState());
    expect(result.current.preset).toBe('7d');
  });

  it('range=custom with NO dates falls back to the default', () => {
    initialParams = new URLSearchParams({ range: 'custom' });
    const { result } = renderHook(() => useDateRangeState());
    expect(result.current.preset).toBe('7d');
  });

  it('range=custom with only start (or only end) falls back to the default', () => {
    initialParams = new URLSearchParams({ range: 'custom', start: '2026-01-01' });
    expect(renderHook(() => useDateRangeState()).result.current.preset).toBe('7d');
    initialParams = new URLSearchParams({ range: 'custom', end: '2026-01-15' });
    expect(renderHook(() => useDateRangeState()).result.current.preset).toBe('7d');
  });

  it('setPreset preserves unrelated URL params', () => {
    initialParams = new URLSearchParams({ filter: 'active', sort: 'date', range: '7d' });
    const { result } = renderHook(() => useDateRangeState());
    act(() => result.current.setPreset('30d'));
    expect(initialParams.get('range')).toBe('30d');
    expect(initialParams.get('filter')).toBe('active');
    expect(initialParams.get('sort')).toBe('date');
  });

  // PRESET_LABELS contract (transplanted from the shadowed legacy suite —
  // NEM-3646 added 'yesterday' to the map; the expectation carries it).
  const labelTests: Array<{ preset: DateRangePreset; expectedLabel: string }> = [
    { preset: '1h', expectedLabel: 'Last hour' },
    { preset: '24h', expectedLabel: 'Last 24 hours' },
    { preset: 'today', expectedLabel: 'Today' },
    { preset: 'yesterday', expectedLabel: 'Yesterday' },
    { preset: '7d', expectedLabel: 'Last 7 days' },
    { preset: '30d', expectedLabel: 'Last 30 days' },
    { preset: '90d', expectedLabel: 'Last 90 days' },
    { preset: 'all', expectedLabel: 'All time' },
    { preset: 'custom', expectedLabel: 'Custom' },
  ];

  it.each(labelTests)('label "$preset" reads "$expectedLabel"', ({ preset, expectedLabel }) => {
    const { result } = renderHook(() => useDateRangeState({ defaultPreset: preset }));
    expect(result.current.presetLabel).toBe(expectedLabel);
  });

  it('PRESET_LABELS exports exactly the shipped label map', () => {
    expect(PRESET_LABELS).toEqual({
      '1h': 'Last hour',
      '24h': 'Last 24 hours',
      today: 'Today',
      yesterday: 'Yesterday',
      '7d': 'Last 7 days',
      '30d': 'Last 30 days',
      '90d': 'Last 90 days',
      all: 'All time',
      custom: 'Custom',
    });
  });

  it('persistToUrl=false neither reads nor writes the URL', () => {
    initialParams = new URLSearchParams({ range: '30d' });
    const { result } = renderHook(() =>
      useDateRangeState({ persistToUrl: false, defaultPreset: 'today' })
    );
    expect(result.current.preset).toBe('today'); // URL ignored
    act(() => result.current.setPreset('90d'));
    expect(setSearchParams).not.toHaveBeenCalled();
    expect(initialParams.get('range')).toBe('30d'); // untouched
  });

  it('a custom urlParam reads its own key, leaving others alone', () => {
    initialParams = new URLSearchParams({ events_range: '24h', range: '90d' });
    const { result } = renderHook(() => useDateRangeState({ urlParam: 'events_range' }));
    expect(result.current.preset).toBe('24h');
  });
});

describe('calculatePresetRange (UTC arithmetic, pinned clock)', () => {
  const now = new Date('2026-06-15T14:30:00.000Z');

  it('1h / 24h are wall-clock windows ending at now', () => {
    expect(calculatePresetRange('1h', now).startDate.toISOString()).toBe(
      '2026-06-15T13:30:00.000Z'
    );
    expect(calculatePresetRange('24h', now).startDate.toISOString()).toBe(
      '2026-06-14T14:30:00.000Z'
    );
  });

  it('today spans UTC start-of-day to now', () => {
    const { startDate, endDate } = calculatePresetRange('today', now);
    expect(startDate.toISOString()).toBe('2026-06-15T00:00:00.000Z');
    expect(endDate.toISOString()).toBe(now.toISOString());
  });

  it('yesterday spans full UTC yesterday', () => {
    const { startDate, endDate } = calculatePresetRange('yesterday', now);
    expect(startDate.toISOString()).toBe('2026-06-14T00:00:00.000Z');
    expect(endDate.toISOString()).toBe('2026-06-14T23:59:59.999Z');
  });

  it('7d/30d/90d span start-of-(today-N) to end-of-today', () => {
    expect(calculatePresetRange('7d', now).startDate.toISOString()).toBe(
      '2026-06-09T00:00:00.000Z'
    );
    expect(calculatePresetRange('30d', now).startDate.toISOString()).toBe(
      '2026-05-17T00:00:00.000Z'
    );
    expect(calculatePresetRange('90d', now).startDate.toISOString()).toBe(
      '2026-03-18T00:00:00.000Z'
    );
    expect(calculatePresetRange('7d', now).endDate.toISOString()).toBe('2026-06-15T23:59:59.999Z');
  });

  it('all/custom return now-anchored placeholders (apiParams carry the meaning)', () => {
    expect(calculatePresetRange('all', now)).toEqual({
      startDate: now,
      endDate: now,
    });
    expect(calculatePresetRange('custom', now)).toEqual({
      startDate: now,
      endDate: now,
    });
  });
});
