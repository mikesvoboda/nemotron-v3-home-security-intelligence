/**
 * FE-1 golden path (F2.3): F-012 — the header's red "Disk n%" warning.
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - The row's clause is "sees 'Disk 93%' in red when disk use is at or above
 *   90 %". Header.tsx:403-415 renders data-testid="storage-warning" (title
 *   `Disk usage: X.X% (90% threshold)`, span text-red-400) only when
 *   isCritical && status; isCritical is `usagePercent >= 90` in the store
 *   (storage-status-store.ts:58, :109).
 * - The mechanism the inventory note names — "the header reads a client store
 *   whose only writer is FileOperationsPanel … until that page is opened in
 *   the session the warning cannot appear" — is exactly what this spec turns
 *   into assertions. The store is plain in-memory zustand with NO persist
 *   middleware and clear() is never called from the panel (grep of
 *   FileOperationsPanel.tsx), and the header itself never fetches
 *   /api/system/storage. So: boot at '/' → warning absent; document-load
 *   /settings/storage (App.tsx:301 mounts the panel via SettingsPage's
 *   <Outlet/>) → panel's mount fetchData (FileOperationsPanel.tsx:489-490)
 *   writes the store (its update call, :471-476) → warning appears in the
 *   header ON THE SAME PAGE; SPA-navigating back to '/' → warning SURVIVES
 *   (module state outlives route changes); document RELOAD → warning gone
 *   again (fresh module state; nothing rewrote it). The reload flip is the
 *   evidence the header doesn't poll the endpoint itself.
 * - The branch is disk-dependent: CRITICAL_USAGE_THRESHOLD is data-driven
 *   (the probe stack measured disk_usage_percent 95.98 from
 *   GET /api/system/storage, shutil.disk_usage of the data dir,
 *   backend/api/routes/system.py:3748). On a stack with < 90 % disk the
 *   warning branch is unexercisable, so the spec self-skips at RUNTIME with
 *   the measured number in the reason — never a silent pass.
 * - The number is MIRRORED, not pinned (the F-005 discipline): the header
 *   shows usagePercent.toFixed(0) while the API carries .toFixed(2) and real
 *   disk use drifts between the panel's fetch and this spec's Node-side read,
 *   so the assert is |headerInt − rawPercent| ≤ 1, and the text shape is the
 *   /^Disk \d+%$/ family.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  BOOT_QUIET_MS,
  closedByGuard,
  quietBoot,
  loginAsAdmin,
  readShellHarness,
  seedTourDismissed,
  type ShellHarness,
} from './harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
}

interface StorageStats {
  disk_usage_percent: number;
}

test.describe('golden path: header disk-usage warning @critical', () => {
  test('F-012: the red Disk warning appears only after /settings/storage writes the session store', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    // The row is data-driven: read the backend's own verdict Node-side first.
    const session = await adminSession(h);
    const stats = await api<StorageStats>(h, session, '/api/system/storage');
    test
      .info()
      .skip(
        stats.disk_usage_percent < 90,
        `stack disk is ${stats.disk_usage_percent}% — the >=90 warning branch cannot render here`
      );

    await openShell(page, h);

    // Negative control, session start: the header never polls the endpoint
    // and nothing has written the store yet, so the warning is absent even
    // though the disk is over threshold (95.98% measured on the probe stack).
    await expect(page.getByTestId('storage-warning')).toHaveCount(0);

    // Open the writer: a document load of /settings/storage mounts
    // FileOperationsPanel (App.tsx:301 via SettingsPage's Outlet), whose
    // mount-time fetchData writes the shared store. Document load = boot
    // wave, so the drain is already inside quietBoot.
    await quietBoot(page, h, '/settings/storage');
    const panel = page.getByTestId('file-operations-panel');
    await expect(panel).toBeVisible({ timeout: 30_000 });
    // The panel's own >=85 amber warning (FileOperationsPanel.tsx:601, :688-
    // :696) rides the same fetch; its presence corroborates the percent the
    // store just received.
    await expect(page.getByTestId('disk-usage-warning')).toBeVisible();

    // The row: red Disk warning in the header, on the SAME page the panel
    // wrote from. Text shape + red class + the shipped title format.
    const warning = page.getByTestId('storage-warning');
    await expect(warning).toBeVisible({ timeout: 15_000 });
    const text = (await warning.innerText()).trim();
    expect(text).toMatch(/^Disk \d+%$/);
    await expect(warning.locator('span')).toHaveClass(/text-red-400/);
    await expect(warning).toHaveAttribute('title', /^Disk usage: \d+\.\d% \(90% threshold\)$/);
    // Mirror the live API number rather than pinning it: header rounds to
    // integer, disk drifts between fetches — ±1 is the honest band. (The
    // panel fetched its own value; both came from the same endpoint.)
    const headerPct = Number(/\d+/.exec(text)![0]);
    const fresh = await api<StorageStats>(h, session, '/api/system/storage');
    expect(Math.abs(headerPct - fresh.disk_usage_percent)).toBeLessThanOrEqual(1);

    // SPA navigation back to '/' (sidebar NavLink, monitoring group, which
    // is defaultExpanded — sidebarNav.ts:63): the in-memory store survives
    // route changes and clear() is never called, so the warning KEEPS
    // rendering on the dashboard. This is the row's "in the header" scope.
    await page.getByTestId('nav-group-monitoring').getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(`${h.ui}/`);
    await expect(warning).toBeVisible();
    await expect(warning).toHaveText(text);

    // Flip side, and the proof of mechanism: a RELOAD resets the module
    // store (no persist middleware) and nothing refetches it on '/' — the
    // header never calls /api/system/storage itself — so the warning
    // disappears even on the same over-threshold disk. Reload is a boot
    // wave, so drain first (BOOT_QUIET_MS, harness.ts).
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(warning).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
