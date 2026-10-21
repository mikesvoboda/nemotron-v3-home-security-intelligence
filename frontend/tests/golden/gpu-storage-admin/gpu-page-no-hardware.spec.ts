/**
 * F-176/F-178: unmocked read-only hardware cards, refresh and preview/local controls.
 * F-182: PROVISIONAL history diff/export from two harness-seeded DB rows.
 * The original GPU-less CI assertions remain below the hardware branch.
 */
import { readFile } from 'node:fs/promises';

import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../harness';

const harness = readOpsHarness();

interface GpuList {
  gpus: { index: number; name: string; vram_total_mb: number }[];
}

test.describe('golden path: GPU settings F-176 F-178 and provisional F-182 @regression', () => {
  test.setTimeout(120_000);

  test('the page exercises read-only hardware controls or preserves the empty live probe', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const listed = await api<GpuList>(h, session, '/api/system/gpus');
    if (listed.gpus.length > 0) {
      const initial = await api<{
        strategy: string;
        assignments: {
          service: string;
          gpu_index: number | null;
          vram_budget_override?: number | null;
        }[];
      }>(h, session, '/api/system/gpu-config');
      const writes: string[] = [];
      page.on('request', (request) => {
        if (
          new URL(request.url()).pathname.startsWith('/api/system/gpu-config') &&
          !['GET', 'HEAD'].includes(request.method())
        )
          writes.push(request.method());
      });
      await page.goto(`${h.ui}/settings/gpu`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('gpu-settings-page')).toBeVisible();
      await expect(page.locator('[data-testid^="gpu-device-card-"]')).toHaveCount(
        listed.gpus.length
      );
      for (const gpu of listed.gpus) {
        expect(gpu.vram_total_mb).toBeGreaterThan(0);
        const card = page.getByTestId(`gpu-device-card-${gpu.index}`);
        await expect(card.getByText(gpu.name, { exact: true })).toBeVisible();
        await expect(card.getByText('VRAM Usage', { exact: true })).toBeVisible();
        const assignments = initial.assignments.filter((a) => a.gpu_index === gpu.index);
        if (!assignments.length) await expect(card.getByText('No services assigned')).toBeVisible();
        for (const assignment of assignments) {
          await expect(card.getByText(assignment.service, { exact: true })).toBeVisible();
        }
      }
      const refreshed = page.waitForResponse(
        (r) => new URL(r.url()).pathname === '/api/system/gpus'
      );
      await page.getByRole('button', { name: 'Refresh', exact: true }).click();
      expect((await refreshed).ok()).toBe(true);

      // F-178 changes only local presentation and calls the read-only preview.
      await page.getByTestId('strategy-option-vram_based').click();
      const previewed = page.waitForResponse(
        (r) => new URL(r.url()).pathname === '/api/system/gpu-config/preview'
      );
      await page.getByTestId('preview-strategy-button').click();
      const preview = await previewed;
      expect(preview.ok()).toBe(true);
      expect((await preview.json()).proposed_assignments.length).toBeGreaterThan(0);
      await expect(page.getByText('Proposed Assignments', { exact: true })).toBeVisible();
      await page.getByTestId('assign-all-button').click();
      await page.getByTestId('assign-all-gpu-select').selectOption(String(listed.gpus[0].index));
      await page.getByTestId('assign-all-confirm-button').click();
      await expect(page.getByTestId('assign-all-dialog')).toHaveCount(0);
      const alreadyDefault =
        listed.gpus[0].index === 0 &&
        initial.assignments.every(
          (a) => a.vram_budget_override === null || a.vram_budget_override === undefined
        );
      if (alreadyDefault) {
        await expect(page.getByTestId('reset-defaults-button')).toBeDisabled();
      } else {
        await page.getByTestId('reset-defaults-button').click();
        await page.getByTestId('reset-confirm-button').click();
        await expect(page.getByTestId('reset-confirm-dialog')).toHaveCount(0);
      }
      if (listed.gpus.length === 1) {
        await expect(page.getByTestId('auto-balance-button')).toBeDisabled();
      } else {
        const balanced = page.waitForResponse(
          (r) => new URL(r.url()).pathname === '/api/system/gpu-config/preview'
        );
        await page.getByTestId('auto-balance-button').click();
        expect((await balanced).ok()).toBe(true);
      }
      const current = await api<typeof initial>(h, session, '/api/system/gpu-config');
      expect(current.strategy).toBe(initial.strategy);
      expect(current.assignments).toEqual(initial.assignments);

      // F-182 is PROVISIONAL pending owner ruling. The harness seeds exactly
      // two historical DB rows and deletes those UUIDs afterwards. No save API.
      const history = await api<{
        versions: { version_number: number; description: string | null }[];
      }>(h, session, '/api/system/gpu-config/history');
      const from = history.versions.find((v) => v.description === 'o25-f182-source-provisional');
      const to = history.versions.find((v) => v.description === 'o25-f182-target-provisional');
      if (!from || !to) throw new Error('Provisional F-182 DB fixtures are missing');
      const panel = page.getByTestId('gpu-version-history');
      await panel.getByRole('button', { name: /Version History/ }).click();
      await panel
        .getByTestId(`version-item-${from.version_number}`)
        .getByTitle('Set as compare source')
        .click();
      const compared = page.waitForResponse(
        (r) => new URL(r.url()).pathname === '/api/system/gpu-config/history/diff'
      );
      await panel
        .getByTestId(`version-item-${to.version_number}`)
        .getByTitle('Set as compare target')
        .click();
      const diff = await compared;
      expect(diff.ok()).toBe(true);
      const changes = await diff.json();
      expect(changes.strategy_changed).toBe(true);
      expect(changes.assignment_changes).toHaveLength(1);
      await expect(
        panel.getByRole('heading', {
          name: `Changes: v${from.version_number} → v${to.version_number}`,
        })
      ).toBeVisible();
      await panel.getByTestId(`version-item-${from.version_number}`).click();
      for (const format of ['JSON', 'YAML']) {
        const downloading = page.waitForEvent('download');
        await panel.getByRole('button', { name: `Export ${format}`, exact: true }).click();
        const download = await downloading;
        expect(download.suggestedFilename()).toMatch(format === 'JSON' ? /\.json$/ : /\.ya?ml$/);
        const file = await download.path();
        if (!file) throw new Error('GPU configuration download has no file');
        // The path comes from Playwright's own download object.
        // eslint-disable-next-line security/detect-non-literal-fs-filename
        const text = await readFile(file, 'utf8');
        if (format === 'JSON') expect(JSON.parse(text).strategy).toBe('vram_based');
        else expect(text).toMatch(/strategy:.*vram_based/);
      }
      expect(writes).toEqual([]);
      expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
      return;
    }
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
