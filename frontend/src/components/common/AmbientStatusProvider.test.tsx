/**
 * [r205] The ambient badge shows health as health, and a number only from a
 * real alert count.
 *
 * Why this file exists: `AmbientStatusProvider` had no test of its own, because
 * the behaviour it implemented was entirely derived — health in, a number out —
 * and the derivation WAS the feature. [r205] removes the invented half
 * (`unhealthy -> 3`, `degraded -> 1`, AmbientStatusProvider.tsx:99-108), and the
 * residue is exactly the part that was never pinned: what the badge may print
 * when nothing counted anything.
 *
 * Two observables, one per half of the clause:
 * - the NUMBER half reads `document.title`. `FaviconBadge` is the only writer in
 *   src of `document.title`, and it prefixes `(N) ` when and only when the count
 *   it was handed is > 0 (FaviconBadge.tsx:216-220, pinned by
 *   FaviconBadge.test.tsx). A prefix is therefore a faithful readout of "the
 *   badge printed a number", without asserting on canvas pixels jsdom cannot
 *   rasterize.
 * - the HEALTH half reads `data-threat-category` on the overlay AmbientBackground
 *   already publishes (AmbientBackground.tsx:174). Health must still reach the
 *   page as health; only its masquerade as a count goes away.
 *
 * The `healthy` / no-status / `alertCountOverride` cases are controls, red or
 * green at both ends on purpose: they pin that the override keeps working and
 * that the tint's health channel survives the removal.
 */
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AmbientStatusProvider from './AmbientStatusProvider';

import type { SystemStatus } from '../../hooks/useSystemStatus';

const { useSystemStatusMock, useSettingsMock } = vi.hoisted(() => ({
  useSystemStatusMock: vi.fn(),
  useSettingsMock: vi.fn(),
}));

vi.mock('../../hooks/useSystemStatus', () => ({
  useSystemStatus: () => useSystemStatusMock(),
}));

vi.mock('../../hooks/useSettings', () => ({
  useSettings: () => useSettingsMock(),
}));

const BASE_TITLE = 'Security Dashboard';

const statusWithHealth = (health: SystemStatus['health']): SystemStatus =>
  ({
    health,
    uptime: 3600,
    services: {},
    gpu_utilization: 0,
    gpu_memory_used: 0,
    gpu_memory_total: 1,
    gpu_temperature: 0,
    inference_fps: 0,
    timestamp: new Date().toISOString(),
    isConnected: true,
  }) as unknown as SystemStatus;

/** The number the badge printed, or null when it printed none. */
const printedCount = (): string | null => {
  const match = /^\((\d+)\) /.exec(document.title);
  return match ? match[1] : null;
};

const renderProvider = (props: { alertCountOverride?: number } = {}) =>
  render(
    <AmbientStatusProvider {...props}>
      <div data-testid="child" />
    </AmbientStatusProvider>
  );

describe('AmbientStatusProvider [r205] health is shown as health, a count only when counted', () => {
  let originalTitle: string;

  beforeEach(() => {
    originalTitle = document.title;
    // No canvas stub: FaviconBadge's favicon draw no-ops under jsdom (its own
    // `if (!ctx) return` bails) and logs a "Not implemented" warning, exactly as
    // in FaviconBadge.test.tsx. Nothing here reads pixels — the badge's number
    // is observed through document.title, which the title path still writes.
    // AmbientBackground's reduced-motion check (AmbientBackground.tsx:71).
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: false,
          media: query,
          onchange: null,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          addListener: vi.fn(),
          removeListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })
    );
    useSettingsMock.mockReturnValue({
      ambientEnabled: true,
      faviconBadgeEnabled: true,
    });
  });

  afterEach(() => {
    // This suite asserts on document.title, which FaviconBadge writes. Leaving
    // a `(7) …` behind would leak into whichever file vitest runs next in this
    // worker — FaviconBadge.test.tsx and the golden ambient spec both read it.
    document.title = originalTitle;
    vi.restoreAllMocks();
  });

  it('prints no number when no status has ever arrived, and reads health as unknown-neutral', () => {
    useSystemStatusMock.mockReturnValue({ status: null, isConnected: false });

    renderProvider();

    expect(printedCount()).toBeNull();
    expect(document.title).toBe(BASE_TITLE);
  });

  it.each([
    ['unhealthy', 'critical'],
    ['degraded', 'elevated'],
    ['healthy', 'normal'],
  ] as const)('a %s service prints no number, and shows as %s', (health, category) => {
    useSystemStatusMock.mockReturnValue({
      status: statusWithHealth(health),
      isConnected: true,
    });

    renderProvider();

    // The half [r205] removes: health rendered as a fabricated alert count.
    expect(printedCount()).toBeNull();
    expect(document.title).toBe(BASE_TITLE);
    // The half [r205] keeps: the same health still reaches the page as health.
    expect(screen.getByTestId('ambient-overlay')).toHaveAttribute('data-threat-category', category);
  });

  it('shows a real count exactly as given (alertCountOverride keeps working)', () => {
    useSystemStatusMock.mockReturnValue({
      status: statusWithHealth('unhealthy'),
      isConnected: true,
    });

    renderProvider({ alertCountOverride: 7 });

    expect(printedCount()).toBe('7');
    expect(document.title).toBe(`(7) ${BASE_TITLE}`);
  });

  it('shows a real count of zero as no number', () => {
    useSystemStatusMock.mockReturnValue({
      status: statusWithHealth('unhealthy'),
      isConnected: true,
    });

    renderProvider({ alertCountOverride: 0 });

    expect(printedCount()).toBeNull();
    expect(document.title).toBe(BASE_TITLE);
  });
});
