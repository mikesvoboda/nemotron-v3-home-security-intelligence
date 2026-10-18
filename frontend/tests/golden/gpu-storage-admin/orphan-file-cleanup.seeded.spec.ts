/**
 * F-186 (inventory 3.9, seeded golden project — rulings 127, 187, 196, 217):
 * Storage settings › Clean orphaned files on `/settings/storage` when the
 * seeded harness has planted an unreferenced thumbnail.
 *
 * Why this leg cannot run in the `golden` project: `clean-orphaned-button`
 * mounts only inside `orphaned-files-warning`, and that component returns null
 * when the panel's polled dry-run finds nothing
 * (FileOperationsPanel.tsx:275). On the stock CI stack the scan measures
 * `{"orphaned_count":0,"total_size":0}`, so the control has no target.
 * `scripts/feature_check.py` seed_debug_fixtures() plants
 * `/app/data/thumbnails/seeded-orphan.jpg` (mtime backdated 48 h) and asserts
 * the dry-run scan reports >= 1 before Playwright starts; this file is the UI
 * end of that fixture.
 *
 * The witness is deliberately NOT "the warning disappeared". `fetchData()`
 * sets `orphanedPreview` to null on the ERROR path too (FileOperationsPanel
 * .tsx:453-468 wraps the preview in `.catch(() => null)`), so a vanished
 * warning is equally consistent with a failed POST. What is asserted instead
 * is the app's OWN re-scan: `handleOrphanedCleanup` awaits
 * `triggerOrphanedCleanup()` then `fetchData()` (:535-543), so a successful
 * delete is followed by a second `dry_run=true` POST whose 200 body must
 * report `orphaned_count === 0`. The `cleanup-error` testid is separately
 * pinned absent, which is what closes the error-path ambiguity.
 *
 * Blast radius, measured before writing: `OrphanedFileCleanup` scans ONLY
 * `video_thumbnails_dir` and `clips_directory`
 * (backend/services/cleanup_service.py, `_get_default_storage_paths`), so this
 * real deletion cannot reach the seeded recordings (`data/recordings`,
 * backend/api/routes/debug.py:1346) or the >90% disk fill
 * (`/app/data/.seeded-disk-fill`, feature_check.py:2176) that the
 * `operations/` seeded legs depend on.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, loginAsAdmin, readOpsHarness } from '../harness';

const harness = readOpsHarness();

const SCAN_PATH = '/api/system/cleanup/orphaned-files';

interface OrphanScanBody {
  orphaned_count?: number;
  total_size?: number;
  dry_run?: boolean;
}

test.describe('seeded golden path: clean orphaned files (F-186) @critical', () => {
  // 90 s, matching the sibling storage legs: the panel re-scans on a 30 s
  // interval and one immediate refetch, and the assertions below key on the
  // refetch that FOLLOWS the delete.
  test.setTimeout(90_000);

  test('clicks Clean Up on the planted orphan and the panel re-scan reports zero orphans', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await loginAsAdmin(page, h);

    test.info().annotations.push({
      type: 'seeded-branch',
      description: 'F-186 orphan delete on the planted seeded-orphan.jpg fixture',
    });

    // Observer over the PAGE's own traffic: every orphan-scan POST, tagged by
    // its dry_run query param, with the body the browser actually received.
    // A node-side pre-read would be a different moment (see the header of
    // storage-file-operations.spec.ts for why this batch mirrors page bodies).
    const scans: { dryRun: boolean; status: number; body: OrphanScanBody | null }[] = [];
    page.on('response', (res) => {
      const url = new URL(res.url());
      if (url.pathname !== SCAN_PATH || res.request().method() !== 'POST') return;
      const dryRun = url.searchParams.get('dry_run') !== 'false';
      const status = res.status();
      void res
        .json()
        .then((body) => scans.push({ dryRun, status, body: body as OrphanScanBody }))
        .catch(() => scans.push({ dryRun, status, body: null }));
    });

    await page.goto(`${h.ui}/settings/storage`, { waitUntil: 'domcontentloaded' });
    const panel = page.getByTestId('file-operations-panel');
    await expect(panel).toBeVisible();

    // The fixture's promise, seen through the UI rather than asserted from the
    // harness log: the warning and its button are mounted because the scan
    // found the planted file.
    const warning = page.getByTestId('orphaned-files-warning');
    await expect(warning).toBeVisible({ timeout: 20_000 });
    await expect(warning).toContainText(/Orphaned Files Found/);
    const cleanButton = page.getByTestId('clean-orphaned-button');
    await expect(cleanButton).toHaveText('Clean Up');

    const deleteAt = scans.length;
    await cleanButton.click();

    // The delete call itself: dry_run=false, answered 200.
    await expect
      .poll(() => scans.some((s) => !s.dryRun && s.status === 200), { timeout: 30_000 })
      .toBe(true);

    // The re-scan the component performs after a successful delete: a LATER
    // dry_run POST reporting nothing left. `deleteAt` guards against matching
    // the boot scan that found the orphan in the first place.
    await expect
      .poll(() => scans.slice(deleteAt).some((s) => s.dryRun && s.body?.orphaned_count === 0), {
        timeout: 45_000,
        intervals: [1_000],
      })
      .toBe(true);

    // And the warning it drives is gone, with no error band anywhere in the
    // panel (the error path is what would make a bare disappearance vacuous).
    await expect(warning).toHaveCount(0);
    await expect(panel.getByTestId('cleanup-error')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
