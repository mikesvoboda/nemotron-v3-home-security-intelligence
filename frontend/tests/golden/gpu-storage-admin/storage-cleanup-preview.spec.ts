/**
 * F-185 (inventory 3.9): Run Cleanup on /settings/storage — the confirm modal.
 *
 * Sibling of OP-1's operations/cleanup-preview.spec.ts (F-163), which proved
 * the SAME modal through its /operations host. This file owns the row's own
 * route (/settings/storage, App.tsx:301) and adds what F-163's spec could
 * not: the modal's five count rows asserted as a MIRROR of the preview body
 * the UI itself received, captured by a response observer (page.on('response')
 * reads traffic; it never intercepts — the guard bans route APIs, not
 * listeners). A text-regex spec only proves "some numbers render"; a mirror
 * proves the modal shows exactly what POST /api/system/cleanup?dry_run=true
 * answered, with no drift possible between what was fetched and what is
 * displayed.
 *
 * The walked-to edge is Cancel, like OP-1: the modal's "Delete Data" button
 * fires run_cleanup(), which deletes events/detections/gpu_stats/logs older
 * than the retention window from the SHARED stack the whole golden run reads.
 * Destructive stack wipes belong to F-162's declared job (with its restore
 * contract); two specs deleting serially would make every later spec's data
 * assertions a race. The row's "…; confirms" clause is cited in the PR body's
 * product-notes section as the deliberate golden boundary, not skipped.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, authPost, loginAsAdmin, readOpsHarness } from '../operations/harness';

const harness = readOpsHarness();

interface CleanupPreview {
  events_deleted: number;
  detections_deleted: number;
  gpu_stats_deleted: number;
  logs_deleted: number;
  thumbnails_deleted: number;
  retention_days: number;
  dry_run: boolean;
}

interface CleanupStatus {
  retention_days: number;
}

test.describe('golden path: storage run-cleanup preview modal @critical', () => {
  test.setTimeout(60_000);

  test('Run Cleanup opens a preview modal that mirrors the dry-run the UI fetched, and Cancel deletes nothing', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Backend legs: the dry-run itself must answer (the row's core chain), and
    // its retention window must agree with the cleanup-service status shown by
    // the panel above the modal (same source: backend/services/cleanup_service.py).
    const preview = await authPost<CleanupPreview>(h, session, '/api/system/cleanup?dry_run=true');
    expect(preview.dry_run).toBe(true);
    const status = await api<CleanupStatus>(h, session, '/api/system/cleanup/status');
    expect(preview.retention_days).toBe(status.retention_days);

    // Observer: capture the preview body the PAGE fetches on click.
    let uiPreview: CleanupPreview | null = null;
    page.on('response', (res) => {
      try {
        const u = new URL(res.url());
        if (u.pathname === '/api/system/cleanup' && u.searchParams.get('dry_run') === 'true') {
          void res
            .json()
            .then((b) => {
              uiPreview = b as CleanupPreview;
            })
            .catch(() => {
              /* body unreadable — the poll below will surface the miss */
            });
        }
      } catch {
        /* non-URL-ish response */
      }
    });

    await page.goto(`${h.ui}/settings/storage`, { waitUntil: 'domcontentloaded' });
    const panel = page.getByTestId('file-operations-panel');
    await expect(panel).toBeVisible();

    await panel.getByTestId('cleanup-button').click();
    const modal = page.getByTestId('cleanup-preview-modal');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('Confirm Cleanup');

    // Mirror: the modal must show exactly the body the UI received. The row
    // regexes keep each value attached to its own label (the same \s* idiom
    // OP-1's spec used) so a shuffled or duplicated number cannot pass.
    await expect.poll(() => uiPreview, { timeout: 10_000 }).not.toBeNull();
    const got = uiPreview as CleanupPreview;
    const n = (v: number) => v.toLocaleString();
    await expect(modal).toContainText(new RegExp(`Events:\\s*${n(got.events_deleted)} events`));
    await expect(modal).toContainText(
      new RegExp(`Detections:\\s*${n(got.detections_deleted)} detections`)
    );
    await expect(modal).toContainText(new RegExp(`GPU Stats:\\s*${n(got.gpu_stats_deleted)}`));
    await expect(modal).toContainText(new RegExp(`Logs:\\s*${n(got.logs_deleted)}`));
    await expect(modal).toContainText(
      new RegExp(`Thumbnails:\\s*${n(got.thumbnails_deleted)} files`)
    );
    await expect(modal).toContainText(`Data older than ${got.retention_days} days will be deleted`);
    await expect(modal.getByTestId('confirm-cleanup-button')).toContainText('Delete Data');

    // Cancel at the gated edge — no deletion (see header for why).
    await modal.getByRole('button', { name: 'Cancel' }).click();
    await expect(modal).toHaveCount(0);
    await expect(page.getByTestId('confirm-cleanup-button')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
