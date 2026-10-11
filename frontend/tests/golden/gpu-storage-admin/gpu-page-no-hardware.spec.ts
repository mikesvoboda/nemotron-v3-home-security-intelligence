/**
 * F-176 / F-178 / F-182 (inventory 3.9): the GPU settings page at
 * /settings/gpu — the empty-hardware leg, and the proof of WHY the three
 * rows demote.
 *
 * The CI compose ships a GPU-less backend, and GpuSettingsPage returns an
 * EmptyState branch the moment its GPU list is empty
 * (frontend/src/pages/GpuSettingsPage.tsx:344): "No GPUs Detected" plus a
 * Rescan action, and NOTHING ELSE. The strategy selector, assignment table,
 * batch actions and version history the F-176/F-178/F-182 rows describe are
 * all inside the has-GPU branch (:375-497) — GpuStrategySelector,
 * GpuAssignmentTable, GpuBatchActions, GpuVersionHistory mount only there —
 * so the rows' interactions cannot be performed on this stack, which is the
 * demotion citation. This spec pins that structural fact so a future CI
 * compose WITH a GPU (or a fixture) flips it loudly: every child testid is
 * asserted toHaveCount(0).
 *
 * What IS fully performable here is the row's own first leg — opens the
 * page, sees what the hardware probe found, clicks Refresh/Rescan — so this
 * batch still ships a green path: /api/system/gpus answers {gpus:[]} (the
 * live pynvml probe over a GPU-less container, list_gpus at
 * backend/api/routes/gpu_config.py:628), the page mirrors it, and the Rescan
 * button POSTs /api/system/gpu-config/detect (services/gpuConfigApi.ts;
 * measured 200 {"gpus":[]} in 0.0 s on this stack), after which the
 * observer-counted re-GET of /api/system/gpus proves the click drove real
 * traffic. The two rows' other legs (VRAM cards, strategy preview, version
 * diff — including F-182's /history/diff route, which 500s 'invalid UUID
 * "diff"' from FastAPI path shadowing at gpu_config.py:1501 even when GPUs
 * exist) stay demoted with their own citations in the inventory notes.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';

const harness = readOpsHarness();

interface GpuList {
  gpus: unknown[];
}

test.describe('golden path: gpu settings page with no hardware @regression', () => {
  test.setTimeout(60_000);

  test('the page mirrors the empty live probe, Rescan re-runs it, and the GPU-branch controls provably never mount', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Backend leg: the page's own first query. If a fixture ever gives this
    // stack GPUs, this expect fails and points at this whole file — which is
    // correct: the empty-state partial is only true while the probe is empty.
    const listed = await api<GpuList>(h, session, '/api/system/gpus');
    expect(listed.gpus).toEqual([]);

    // Observer: GET /api/system/gpus calls the page itself makes (mount +
    // post-detect refetch). Node-side api() never lands here.
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

    // EmptyState branch (GpuSettingsPage.tsx:344-370).
    await expect(page.getByText('No GPUs Detected')).toBeVisible();

    // The GPU-branch controls the three rows describe (testids read from
    // components/settings/GpuBatchActions.tsx, GpuVersionHistory.tsx,
    // GpuStrategySelector.tsx, GpuAssignmentTable.tsx — all mounted only in
    // the has-GPU render): each is absent HERE, structurally.
    for (const id of [
      'gpu-strategy-selector',
      'gpu-assignment-table',
      'assignment-table',
      'gpu-batch-actions',
      'gpu-version-history',
    ]) {
      await expect(page.getByTestId(id)).toHaveCount(0);
    }

    // "clicks Refresh" (row F-176) surfaces here as the EmptyState's Rescan
    // GPUs action, which POSTs the detect probe and refetches the list.
    const atClick = gpusFetches;
    expect(atClick).toBeGreaterThanOrEqual(1); // mount fetch already counted
    await page.getByRole('button', { name: 'Rescan GPUs' }).click();
    await expect
      .poll(() => gpusFetches, { timeout: 15_000, intervals: [500] })
      .toBeGreaterThan(atClick);

    // And the result is honest: still empty, still the EmptyState.
    await expect(page.getByText('No GPUs Detected')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
