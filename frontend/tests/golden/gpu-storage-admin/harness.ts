/**
 * Local helpers for the gpu-storage-admin golden batch (F2.3, ops cell A).
 *
 * Everything generic comes from ../operations/harness; the one addition here
 * is openAdminSection. Why a second opener is needed (read from the two
 * component files, not guessed): operations/harness.ts:208 openSection builds
 * its ids as `${sectionId}-section` / `${sectionId}-section-toggle`, which is
 * the scheme SystemMonitoringPage's sections use. AdminSettings passes
 * PLAIN ids to the same CollapsibleSection component —
 * `data-testid="admin-maintenance"` and the derived
 * `data-testid="admin-maintenance-toggle"` (CollapsibleSection.tsx:59,77: the
 * toggle is the root id plus `-toggle`).
 *
 * Opening is not cosmetic here: CollapsibleSection wraps its panel in
 * <Transition show={isExpanded}> (CollapsibleSection.tsx:98-114), so a closed
 * section's children are NOT in the DOM — LoggingSettings' controls and
 * OrphanCleanupPanel's sliders only exist after the toggle is clicked. The
 * helper therefore takes the testid of a child that is mounted ONLY inside
 * that section's panel and waits for it, which doubles as "the click worked"
 * (a heuristic DOM probe would be guessing at markup the suite doesn't own).
 */
import { expect, type Page } from '@playwright/test';

export * from '../operations/harness';

/**
 * Expand an AdminSettings collapsible section by its plain data-testid and
 * wait for `mountedWhenOpenTestId` — a child that renders only while the
 * section's Disclosure.Panel is mounted. Idempotent: Feature Toggles /
 * System Config / Maintenance default to open (AdminSettings.tsx:191-193),
 * so the click is skipped when the child is already there.
 */
export async function openAdminSection(
  page: Page,
  sectionId: string,
  mountedWhenOpenTestId: string
): Promise<void> {
  const root = page.getByTestId(sectionId);
  await expect(root).toBeVisible();
  const child = root.getByTestId(mountedWhenOpenTestId);
  if ((await child.count()) === 0) {
    const toggle = page.getByTestId(`${sectionId}-toggle`);
    await expect(toggle).toBeVisible();
    await toggle.click();
  }
  await expect(child).toBeVisible({ timeout: 5_000 });
}
