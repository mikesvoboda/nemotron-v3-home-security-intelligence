/**
 * F-192 (inventory 3.9): Admin › Maintenance › Clear Cache.
 *
 * The row is fully performable on the CI stack and this spec proves it
 * end to end: click Clear Cache, confirm in the ConfirmDialog, and the page
 * must show a "Cache cleared" toast carrying the endpoint's own key count —
 * asserted as a MIRROR of the POST /api/admin/maintenance/clear-cache body
 * the UI received (response observer; page.on('response') never intercepts,
 * so the golden guard stays intact). The mirror matters because the toast's
 * description is exactly result.message ("Cleared N cache keys across M cache
 * types", AdminSettings.tsx:350-352 fed by backend/api/routes/admin.py:1084):
 * a spec that just waits for the word "cleared" would pass on a toast lying
 * about the count.
 *
 * Cache clearing is the one Maintenance action whose blast radius is the
 * Redis cache the app repopulates — no table or file dies — so unlike the
 * F-185/F-194 destructive edges, this spec CONFIRMS rather than cancels, and
 * does it on a stack where the measured cache occupancy is small (last sweep:
 * keys_cleared 0, message "Cleared 0 cache keys across 0 cache types").
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';
import { openAdminSection } from './harness';

const harness = readOpsHarness();

interface ClearCacheBody {
  keys_cleared: number;
  cache_types_cleared?: number;
  message: string;
}

test.describe('golden path: admin maintenance clear cache @critical', () => {
  test.setTimeout(60_000);

  test('confirming Clear Cache runs the POST and the toast carries the endpoint message', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await loginAsAdmin(page, h);

    // Observer: capture the clear-cache body the PAGE triggers.
    let cleared: ClearCacheBody | null = null;
    page.on('response', (res) => {
      try {
        if (new URL(res.url()).pathname === '/api/admin/maintenance/clear-cache') {
          void res
            .json()
            .then((b) => {
              cleared = b as ClearCacheBody;
            })
            .catch(() => {
              /* unreadable body — the poll below surfaces the miss */
            });
        }
      } catch {
        /* non-URL-ish response */
      }
    });

    await page.goto(`${h.ui}/settings/admin`, { waitUntil: 'domcontentloaded' });
    await openAdminSection(page, 'admin-maintenance', 'btn-cache-clear');

    await page.getByTestId('btn-cache-clear').click();
    const dialog = page.getByTestId('confirm-dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Clear Cache');
    await expect(dialog).toContainText('purge all cached data from Redis');

    // The dialog's confirm button carries confirmLabel="Clear Cache"
    // (AdminSettings.tsx:936); the trigger button is outside this root, so
    // the role query inside the dialog is unambiguous.
    await dialog.getByRole('button', { name: 'Clear Cache' }).click();
    await expect(dialog).toHaveCount(0); // handleCacheClear closes it in finally (:359)

    await expect.poll(() => cleared, { timeout: 10_000 }).not.toBeNull();
    const body = cleared as ClearCacheBody;
    expect(typeof body.keys_cleared).toBe('number');
    expect(body.message).toMatch(/Cleared \d+ cache keys/);

    const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Cache cleared' });
    await expect(toast).toBeVisible();
    await expect(toast).toContainText(body.message);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
