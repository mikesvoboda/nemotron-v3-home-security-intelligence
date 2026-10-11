/**
 * F-148 (inventory 3.8): Performance history with a time-range picker.
 *
 * The harness stack snapshots system metrics roughly every 45 s, so a stack
 * younger than ~a minute legitimately renders the "No performance data
 * available" empty state — the DOM probe caught exactly that young-stack
 * reading, while minutes later the SAME panel charted 2 snapshots and answered
 * a 60m click with a real refetch. This spec therefore waits (Node-side) for
 * the first snapshot in the panel's own window before loading the page, then
 * pins both legs: chart-over-data, and a time-range click that refetches.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

interface HistoryBody {
  snapshots: unknown[];
  count?: number;
}

test.describe('golden path: performance history @critical', () => {
  test.setTimeout(150_000); // worst case: wait for the first snapshot cadence

  test('charts real snapshots and re-fetches on a time-range change', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Wait for data in the panel's DEFAULT window (5m) — same endpoint and
    // param the browser will use, so the page cannot race the sampler.
    const deadline = Date.now() + 100_000;
    for (;;) {
      const body = await api<HistoryBody>(
        h,
        session,
        '/api/system/performance/history?time_range=5m',
      );
      if ((body.snapshots?.length ?? 0) > 0) break;
      if (Date.now() > deadline) break;
      await new Promise((r) => setTimeout(r, 3_000));
    }

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'performance-history');
    const section = page.getByTestId('performance-history-section');
    await expect(page.getByTestId('performance-history')).toBeVisible();
    await expect(section).not.toContainText('No performance data available');

    // Time-range leg: 60m must re-fetch (measured: 200 + chart re-render).
    await page.locator('button', { hasText: '60m' }).first().click();
    const respPromise = page
      .waitForResponse((r) => r.url().includes('performance/history?time_range=60m'), {
        timeout: 15_000,
      })
      .catch(() => null);
    await expect(respPromise).resolves.not.toBeNull();
    await expect(page.getByTestId('performance-history-empty')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
