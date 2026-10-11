/**
 * F-149 (inventory 3.8): GPU utilisation/memory/temperature over the last 300
 * samples.
 *
 * This is the one history panel whose content is REAL on a virgin harness
 * stack: the metrics supervisor samples GPU stats from the start (mock GPU dev
 * mode), and the probe measured /api/system/gpu/history growing 225 → 243
 * items while idle. So the golden path asserts a chart over real samples,
 * with the sample count proven from the endpoint first.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: gpu history @critical', () => {
  test.setTimeout(90_000);

  test('the chart renders over real historical samples', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // The sampler needs a few cycles after backend start; the golden stage
    // runs minutes after compose-up, so one poll covers any cold start.
    const deadline = Date.now() + 60_000;
    let history: { items?: unknown[]; count?: number } = {};
    for (;;) {
      history = await api<{ items?: unknown[]; count?: number }>(
        h,
        session,
        '/api/system/gpu/history',
      );
      const n = history.items?.length ?? history.count ?? 0;
      if (n > 0) break;
      if (Date.now() > deadline) break;
      await new Promise((r) => setTimeout(r, 2_000));
    }
    expect((history.items ?? []).length + (history.count ?? 0)).toBeGreaterThan(0);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'gpu-history');
    await expect(page.getByTestId('gpu-history')).toBeVisible();
    await expect(page.getByTestId('gpu-history-chart')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
