/**
 * F-163 (inventory 3.8): the File Operations section on /operations — "same
 * component and actions as Storage settings (F-184 to F-186)".
 *
 * What this proves and where it stops: the section is default-COLLAPSED
 * (useSystemPageSections DEFAULT_SECTION_STATES), so opening it is part of the
 * path. The panel's three read legs (storage usage, active exports, cleanup
 * service status) all fill from live endpoints — measured on the harness
 * stack: storage-usage-section renders, cleanup-summary reads Status: Running
 * with retention 30 days. Then the row's destructive action is walked to its
 * gated edge: Run Cleanup POSTs a PREVIEW (POST /api/system/cleanup's dry
 * read, measured) and the Confirm Cleanup modal lists the counts behind a
 * "Delete Data" button — and the golden path CLICKS CANCEL. Deleting shared
 * stack data is F-162's declared job (with its restore contract); two specs
 * wiping the DB serially would make every later spec's data assertions a race.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: file operations cleanup preview @critical', () => {
  test.setTimeout(60_000);

  test('panel reads live state and the cleanup preview modal gates Delete Data', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await loginAsAdmin(page, h);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'file-operations');
    const panel = page.getByTestId('file-operations-panel-section');
    await expect(panel).toBeVisible();

    // Read legs (FileOperationsPanel.tsx): storage usage and the cleanup
    // service summary both render only once their endpoints answered.
    await expect(panel.getByTestId('storage-usage-section')).toBeVisible();
    const summary = panel.getByTestId('cleanup-summary');
    await expect(summary).toBeVisible();
    await expect(summary).toContainText(/Status:/);
    await expect(summary).toContainText(/Retention:/);

    // Preview leg: the button POSTs the dry-run cleanup preview and the modal
    // renders its counts (FileOperationsPanel.tsx:325-409).
    await panel.getByTestId('cleanup-button').click();
    const modal = page.getByTestId('cleanup-preview-modal');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('Confirm Cleanup');
    await expect(modal).toContainText(/Events:\s*[\d,]+ events/);
    await expect(modal).toContainText(/Detections:\s*[\d,]+ detections/);
    await expect(modal.getByTestId('confirm-cleanup-button')).toContainText('Delete Data');

    // Cancel at the gated edge — no deletion (see header for why).
    await modal.getByRole('button', { name: 'Cancel' }).click();
    await expect(modal).toHaveCount(0);
    await expect(page.getByTestId('confirm-cleanup-button')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
