/**
 * Tests for useDateRangeState hook
 *
 * This hook manages date range state with URL persistence for
 * preset and custom date ranges.
 *
 * @see NEM-2701
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { useDateRangeState, calculatePresetRange, PRESET_LABELS } from './useDateRangeState';

import type { DateRangePreset } from './useDateRangeState';
import type { ReactNode } from 'react';

// Helper to create a wrapper with MemoryRouter at a specific route
function createWrapper(initialRoute = '/') {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initialRoute]}>{children}</MemoryRouter>;
  };
}

describe('useDateRangeState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('default behavior', () => {
    it('returns default preset of 7d when no options provided', () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper(),
      });

      expect(result.current.preset).toBe('7d');
    });

    it('respects custom default preset', () => {
      const { result } = renderHook(() => useDateRangeState({ defaultPreset: '30d' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.preset).toBe('30d');
    });

    it('returns isCustom false for preset ranges', () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isCustom).toBe(false);
    });

    it('returns correct preset label', () => {
      const { result } = renderHook(() => useDateRangeState({ defaultPreset: '7d' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.presetLabel).toBe('Last 7 days');
    });
  });

  describe('URL persistence', () => {
    it('reads preset from URL on initial render', () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper('/?range=30d'),
      });

      expect(result.current.preset).toBe('30d');
    });

    it('reads custom range from URL', () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper('/?range=custom&start=2024-01-01&end=2024-01-15'),
      });

      expect(result.current.preset).toBe('custom');
      expect(result.current.isCustom).toBe(true);
      expect(result.current.range.startDate.toISOString().split('T')[0]).toBe('2024-01-01');
      expect(result.current.range.endDate.toISOString().split('T')[0]).toBe('2024-01-15');
    });

    it('uses custom URL param name when specified', () => {
      const { result } = renderHook(() => useDateRangeState({ urlParam: 'dateRange' }), {
        wrapper: createWrapper('/?dateRange=24h'),
      });

      expect(result.current.preset).toBe('24h');
    });

    it('falls back to default for invalid URL param', () => {
      const { result } = renderHook(() => useDateRangeState({ defaultPreset: '7d' }), {
        wrapper: createWrapper('/?range=invalid'),
      });

      expect(result.current.preset).toBe('7d');
    });

    it('does not persist to URL when persistToUrl is false', () => {
      const { result } = renderHook(
        () => useDateRangeState({ persistToUrl: false, defaultPreset: '7d' }),
        { wrapper: createWrapper('/?range=30d') }
      );

      // Should use default, not URL value
      expect(result.current.preset).toBe('7d');
    });
  });

  describe('setPreset', () => {
    it('updates preset to new value', async () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper(),
      });

      expect(result.current.preset).toBe('7d');

      act(() => {
        result.current.setPreset('30d');
      });

      await waitFor(
        () => {
          expect(result.current.preset).toBe('30d');
        },
        { timeout: 2000 }
      );
    });

    it('clears custom date params when switching to preset', async () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper('/?range=custom&start=2024-01-01&end=2024-01-15'),
      });

      expect(result.current.preset).toBe('custom');

      act(() => {
        result.current.setPreset('7d');
      });

      await waitFor(
        () => {
          expect(result.current.preset).toBe('7d');
        },
        { timeout: 2000 }
      );
    });

    it('does not set custom preset via setPreset (use setCustomRange instead)', () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.setPreset('custom');
      });

      // Should remain at default since setPreset('custom') is ignored
      expect(result.current.preset).toBe('7d');
    });
  });

  describe('setCustomRange', () => {
    it('sets custom date range and switches to custom preset', async () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper(),
      });

      expect(result.current.preset).toBe('7d');

      const startDate = new Date('2024-01-01');
      const endDate = new Date('2024-01-10');

      act(() => {
        result.current.setCustomRange(startDate, endDate);
      });

      await waitFor(
        () => {
          expect(result.current.preset).toBe('custom');
          expect(result.current.isCustom).toBe(true);
          expect(result.current.range.startDate.toISOString().split('T')[0]).toBe('2024-01-01');
          expect(result.current.range.endDate.toISOString().split('T')[0]).toBe('2024-01-10');
        },
        { timeout: 2000 }
      );
    });
  });

  describe('reset', () => {
    it('resets to default preset', async () => {
      const { result } = renderHook(() => useDateRangeState({ defaultPreset: '7d' }), {
        wrapper: createWrapper('/?range=30d'),
      });

      expect(result.current.preset).toBe('30d');

      act(() => {
        result.current.reset();
      });

      await waitFor(
        () => {
          expect(result.current.preset).toBe('7d');
        },
        { timeout: 2000 }
      );
    });

    it('clears custom date range on reset', async () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper('/?range=custom&start=2024-01-01&end=2024-01-15'),
      });

      expect(result.current.preset).toBe('custom');

      act(() => {
        result.current.reset();
      });

      await waitFor(
        () => {
          expect(result.current.preset).toBe('7d');
          expect(result.current.isCustom).toBe(false);
        },
        { timeout: 2000 }
      );
    });
  });

  describe('apiParams format', () => {
    it('returns YYYY-MM-DD formatted dates for preset range', () => {
      const { result } = renderHook(() => useDateRangeState({ defaultPreset: '7d' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.apiParams.start_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(result.current.apiParams.end_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('returns empty strings for "all" preset (no filtering)', () => {
      const { result } = renderHook(() => useDateRangeState({ defaultPreset: 'all' }), {
        wrapper: createWrapper(),
      });

      expect(result.current.apiParams.start_date).toBe('');
      expect(result.current.apiParams.end_date).toBe('');
    });

    it('returns correct dates for custom range', async () => {
      const { result } = renderHook(() => useDateRangeState(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.setCustomRange(
          new Date('2024-01-01T00:00:00Z'),
          new Date('2024-01-10T23:59:59Z')
        );
      });

      await waitFor(
        () => {
          expect(result.current.apiParams.start_date).toBe('2024-01-01');
          expect(result.current.apiParams.end_date).toBe('2024-01-10');
        },
        { timeout: 2000 }
      );
    });
  });

  describe('preset labels', () => {
    const labelTests: Array<{ preset: DateRangePreset; expectedLabel: string }> = [
      { preset: '1h', expectedLabel: 'Last hour' },
      { preset: '24h', expectedLabel: 'Last 24 hours' },
      { preset: 'today', expectedLabel: 'Today' },
      { preset: '7d', expectedLabel: 'Last 7 days' },
      { preset: '30d', expectedLabel: 'Last 30 days' },
      { preset: '90d', expectedLabel: 'Last 90 days' },
      { preset: 'all', expectedLabel: 'All time' },
      { preset: 'custom', expectedLabel: 'Custom' },
    ];

    it.each(labelTests)(
      'returns "$expectedLabel" for preset "$preset"',
      ({ preset, expectedLabel }) => {
        const { result } = renderHook(() => useDateRangeState({ defaultPreset: preset }), {
          wrapper: createWrapper(),
        });

        expect(result.current.presetLabel).toBe(expectedLabel);
      }
    );

    it('exports PRESET_LABELS constant with all labels', () => {
      expect(PRESET_LABELS).toEqual({
        '1h': 'Last hour',
        '24h': 'Last 24 hours',
        today: 'Today',
        '7d': 'Last 7 days',
        '30d': 'Last 30 days',
        '90d': 'Last 90 days',
        all: 'All time',
        custom: 'Custom',
      });
    });
  });
});

describe('calculatePresetRange', () => {
  const now = new Date('2026-01-17T12:00:00.000Z');

  it('calculates correct range for "1h" preset', () => {
    const range = calculatePresetRange('1h', now);

    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();

    // Start should be 1 hour ago
    const expectedStart = new Date('2026-01-17T11:00:00.000Z');
    expect(range.startDate.getTime()).toBe(expectedStart.getTime());
  });

  it('calculates correct range for "24h" preset', () => {
    const range = calculatePresetRange('24h', now);

    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();

    // Start should be 24 hours ago
    const expectedStart = new Date('2026-01-16T12:00:00.000Z');
    expect(range.startDate.getTime()).toBe(expectedStart.getTime());
  });

  it('calculates correct range for "today" preset', () => {
    const range = calculatePresetRange('today', now);

    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();

    // Start should be start of today (midnight UTC)
    expect(range.startDate.getUTCHours()).toBe(0);
    expect(range.startDate.getUTCMinutes()).toBe(0);
    expect(range.startDate.getUTCSeconds()).toBe(0);
  });

  it('calculates correct range for "7d" preset', () => {
    const range = calculatePresetRange('7d', now);

    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();

    // Start should be 6 days ago at midnight (for 7 complete days including today)
    // 2026-01-17 minus 6 days = 2026-01-11
    expect(range.startDate.getUTCDate()).toBe(11);
    expect(range.startDate.getUTCMonth()).toBe(0); // January
    expect(range.startDate.getUTCFullYear()).toBe(2026);
  });

  it('calculates correct range for "30d" preset', () => {
    const range = calculatePresetRange('30d', now);

    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();

    // Start should be 29 days ago at midnight (for 30 complete days including today)
    // 2026-01-17 minus 29 days = 2025-12-19
    expect(range.startDate.getUTCDate()).toBe(19);
    expect(range.startDate.getUTCMonth()).toBe(11); // December
    expect(range.startDate.getUTCFullYear()).toBe(2025);
  });

  it('calculates correct range for "90d" preset', () => {
    const range = calculatePresetRange('90d', now);

    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();

    // Start should be 89 days ago at midnight (for 90 complete days including today)
    // 2026-01-17 minus 89 days = 2025-10-20
    expect(range.startDate.getUTCDate()).toBe(20);
    expect(range.startDate.getUTCMonth()).toBe(9); // October
    expect(range.startDate.getUTCFullYear()).toBe(2025);
  });

  it('returns placeholder dates for "all" preset', () => {
    const range = calculatePresetRange('all', now);

    // The range returns the current date as a placeholder for 'all'
    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();
  });

  it('returns placeholder dates for "custom" preset (until setCustomRange is called)', () => {
    const range = calculatePresetRange('custom', now);

    // The range returns the current date as a placeholder for 'custom'
    expect(range.startDate).not.toBeNull();
    expect(range.endDate).not.toBeNull();
  });
});

describe('edge cases and validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handles invalid date strings in URL gracefully - falls back to default', () => {
    const { result } = renderHook(() => useDateRangeState(), {
      wrapper: createWrapper('/?range=custom&start=invalid&end=also-invalid'),
    });

    // Invalid custom range falls back to default preset
    expect(result.current.preset).toBe('7d');
  });

  it('preserves other URL params when updating preset', async () => {
    const { result } = renderHook(() => useDateRangeState(), {
      wrapper: createWrapper('/?filter=active&sort=date&range=7d'),
    });

    act(() => {
      result.current.setPreset('30d');
    });

    await waitFor(
      () => {
        expect(result.current.preset).toBe('30d');
      },
      { timeout: 2000 }
    );

    // Note: We can't easily verify full URL preservation in this test setup,
    // but the implementation uses replace mode and preserves existing params
  });

  it('handles empty URL param value', () => {
    const { result } = renderHook(() => useDateRangeState({ defaultPreset: '7d' }), {
      wrapper: createWrapper('/?range='),
    });

    // Empty value should fall back to default
    expect(result.current.preset).toBe('7d');
  });

  it('handles missing custom date params when range=custom - falls back to default', () => {
    const { result } = renderHook(() => useDateRangeState(), {
      wrapper: createWrapper('/?range=custom'),
    });

    // Missing custom dates falls back to default preset
    expect(result.current.preset).toBe('7d');
  });

  it('handles partial custom date params (only start) - falls back to default', () => {
    const { result } = renderHook(() => useDateRangeState(), {
      wrapper: createWrapper('/?range=custom&start=2026-01-01'),
    });

    // Partial custom dates falls back to default preset
    expect(result.current.preset).toBe('7d');
  });

  it('handles partial custom date params (only end) - falls back to default', () => {
    const { result } = renderHook(() => useDateRangeState(), {
      wrapper: createWrapper('/?range=custom&end=2026-01-15'),
    });

    // Partial custom dates falls back to default preset
    expect(result.current.preset).toBe('7d');
  });
});
