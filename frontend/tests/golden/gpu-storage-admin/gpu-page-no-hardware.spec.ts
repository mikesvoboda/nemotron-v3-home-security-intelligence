/**
 * F-176 / F-178 / F-182 (inventory 3.9): the GPU settings page at
 * /settings/gpu — the empty-hardware leg, and the proof of WHY the three
 * rows demote.
 *
 * The CI compose ships a GPU-less backend, and GpuSettingsPage returns an
 * EmptyState branch the moment its GPU list is empty
 * (frontend/src/pages/GpuSettingsPage.tsx): "No GPUs Detected" plus a
 * Refresh action, and NOTHING ELSE. The strategy selector, batch actions
 * and version history the F-176/F-178/F-182 rows describe are all inside the
 * has-GPU branch — GpuStrategySelector, GpuBatchActions, GpuVersionHistory
 * mount only there — so the rows' interactions cannot be performed on this
 * stack, which is the demotion citation. This spec pins that structural fact
 * so a future CI compose WITH a GPU (or a fixture) flips it loudly: every
 * child testid is asserted toHaveCount(0).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../harness';

const harness = readOpsHarness();

interface GpuList {
  gpus: unknown[];
}

test.describe('golden path: gpu settings page with no hardware @regression', () => {
  test.setTimeout(60_000);

  test('the page mirrors the empty live probe, Refresh re-runs it, and the GPU-branch controls provably never mount', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const listed = await api<GpuList>(h, session, '/api/system/gpus');
    expect(listed.gpus).toEqual([]);

    let gpusFetches = 0;
    page.on('response', (res) => {
      try {
        if (new URL(res.url()).pathname === '/api/system/gpus') gpusFetches += 1;
      } catch {
        /* non-URL-ish response */
      }
    });

    await page.goto(`${h.ui}/settings/gpu`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('gpu-settings-page')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'GPU Settings' })).toBeVisible();

    await expect(page.getByText('No GPUs Detected')).toBeVisible();

    for (const id of ['gpu-strategy-selector', 'gpu-batch-actions', 'gpu-version-history']) {
      await expect(page.getByTestId(id)).toHaveCount(0);
    }

    const atClick = gpusFetches;
    expect(atClick).toBeGreaterThanOrEqual(1);
    await page.getByRole('button', { name: 'Refresh' }).click();
    await expect
      .poll(() => gpusFetches, { timeout: 15_000, intervals: [500] })
      .toBeGreaterThan(atClick);

    await expect(page.getByText('No GPUs Detected')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
