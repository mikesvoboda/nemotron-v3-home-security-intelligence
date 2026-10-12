/**
 * F-194 (inventory 3.9): Admin › Maintenance › Orphan cleanup panel.
 *
 * The preview leg is fully live on the CI stack: the panel's Preview button
 * POSTs /api/admin/cleanup/orphans with dry_run=true (OrphanCleanupPanel
 * .tsx:315-333 via useAdminMutations.ts:276) and the Results grid mounts from
 * the response. This spec mirrors each results tile against the body the UI
 * itself received (response observer — reading traffic is guard-safe), so a
 * number rendered wrong or from a stale run fails. It also pins the two
 * parameter controls the row's "sets age/size limits" clause runs through
 * (SliderInput defaults 24 h / 10 GB → their formatted value labels).
 *
 * The row's last clause is "then Clean Up with confirmation" — walked to the
 * ConfirmDialog ("Delete Files", :475-486) and CANCELLED, the OP-1
 * cleanup-preview precedent: a dry_run=false run deletes files from the
 * shared stack's data dir, and destructive stack wipes are F-162's declared
 * job. The observer count doubles as proof the cancel click fired no second
 * POST — the clean-up request exists only behind the dialog's confirm.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';
import { openAdminSection } from './harness';

const harness = readOpsHarness();

interface OrphansBody {
  scanned_files: number;
  orphaned_files: number;
  deleted_files: number;
  deleted_bytes_formatted?: string;
  dry_run: boolean;
}

test.describe('golden path: admin orphan cleanup preview @critical', () => {
  test.setTimeout(60_000);

  test('Preview mirrors the dry-run body into the results grid, and Clean Up stops at its confirm dialog', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await loginAsAdmin(page, h);

    // Observer: every POST this page makes to the orphans endpoint, plus the
    // last body seen (preview and clean-up share the path; dry_run separates).
    const orphansPosts: OrphansBody[] = [];
    page.on('response', (res) => {
      try {
        if (new URL(res.url()).pathname === '/api/admin/cleanup/orphans') {
          void res
            .json()
            .then((b) => orphansPosts.push(b as OrphansBody))
            .catch(() => {
              /* unreadable body — the poll below surfaces the miss */
            });
        }
      } catch {
        /* non-URL-ish response */
      }
    });

    await page.goto(`${h.ui}/settings/admin`, { waitUntil: 'domcontentloaded' });
    await openAdminSection(page, 'admin-maintenance', 'orphan-cleanup-panel');
    const panel = page.getByTestId('orphan-cleanup-panel');
    await expect(panel).toBeVisible();

    // Parameter controls at their shipped defaults (SliderInput:386-414):
    // 24 h formats "1 day", 10 GB formats "10.0 GB".
    await expect(page.getByTestId('min-age-hours-slider-value')).toHaveText('1 day');
    await expect(page.getByTestId('max-delete-gb-slider-value')).toHaveText('10.0 GB');

    // Preview leg: click, wait for the page's own POST to answer.
    await page.getByTestId('btn-preview-cleanup').click();
    await expect.poll(() => orphansPosts.length, { timeout: 15_000 }).toBe(1);
    const preview = orphansPosts[0];
    expect(preview.dry_run).toBe(true);

    // Results grid mirrors the body (ResultsDisplay:200-246 — dry-run labels
    // are "Would Delete"/"Would Free").
    await expect(page.getByTestId('result-scanned-files')).toHaveText(
      preview.scanned_files.toLocaleString()
    );
    await expect(page.getByTestId('result-orphaned-files')).toHaveText(
      preview.orphaned_files.toLocaleString()
    );
    await expect(page.getByTestId('result-deleted-files')).toHaveText(
      `${preview.deleted_files.toLocaleString()} files`
    );
    if (preview.deleted_bytes_formatted) {
      await expect(page.getByTestId('result-deleted-bytes')).toHaveText(
        preview.deleted_bytes_formatted
      );
    }

    // Clean Up leg to the gated edge: the dialog names the preview counts in
    // its description (OrphanCleanupPanel.tsx:477), then Cancel — and Cancel
    // must NOT produce a second POST (asserted after the dialog closes).
    await page.getByTestId('btn-run-cleanup').click();
    const dialog = page.getByTestId('confirm-dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Confirm Orphan Cleanup');
    await expect(dialog).toContainText('Delete Files');
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).toHaveCount(0);

    // Give a stray POST a chance to land, then require the count unchanged.
    await page.waitForTimeout(1_500);
    expect(orphansPosts.length).toBe(1);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
