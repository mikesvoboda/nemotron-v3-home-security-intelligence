/**
 * FE-1 golden path (F2.3): F-017 — sidebar nav clicks, remembered group +
 * sidebar collapse, and the mobile bottom bar / slide-out menu.
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * Decided from shipped code before writing (each claim cites where), and TWO
 * of the obvious instruments turned out to be traps, so this spec measures
 * state instead of class names:
 *
 * - Clause 1 (click an item → go to a page): NavItems are React Router
 *   NavLinks inside `nav-group-content-<group>` (Sidebar.tsx:102-142); the
 *   monitoring group is defaultExpanded (sidebarNav.ts:61-74) so Timeline is
 *   reachable without any prior click.
 * - Clause 2 (collapse groups, remembered): the group header
 *   `nav-group-header-<id>` carries aria-expanded (:109-111) and content
 *   collapses via max-h-0 (:126); handleToggleGroup writes the WHOLE map to
 *   localStorage 'sidebar-expansion-state' (JSON, :26-30 + sidebarNav.ts:57),
 *   and the mount initializer re-reads it (loadExpansionState :14-24).
 *   'analytics' is the group under test because it is defaultExpanded TRUE
 *   (:78-80) and NOT the active route — the active-route effect (:220-236)
 *   force-expands and SAVES the group that contains the current path, so
 *   asserting on the active group would measure that effect, not memory.
 *   "Remembered" is proven across a document RELOAD.
 * - Clause 3 (collapse the sidebar, remembered) is where the naive assert
 *   lies: `isCollapsed = forceCollapsed ?? (isTablet || (isDesktop &&
 *   userCollapsed))` (:204) and showExpanded = !isCollapsed || isHovered
 *   (:262), with onMouseEnter setting isHovered whenever isCollapsed (:271).
 *   So (a) between 640 and 1023 the rail is FORCE-collapsed no matter what
 *   the user chose (isTablet, useViewport.ts:125) — the desktop-only toggle
 *   (:288) cannot even render there — and (b) at desktop width, clicking the
 *   toggle leaves the pointer INSIDE the <aside>, which immediately
 *   re-expands it, so `w-16` measured right after the click would fail and
 *   `data-collapsed` would read false. The honest instrument is therefore the
 *   jar (localStorage 'sidebar-collapsed-state' carries the 4-character string
 *   'true', the output of JSON.stringify(true) at :179-185 — measured, first
 *   draft asserted the quoted form and the run said so) plus the RENDERED width
 *   after the pointer has
 *   left the rail, plus the width after a RELOAD (fresh mount ⇒ isHovered
 *   false, so the class is the restored state, not a hover artifact).
 * - Clause 4a (mobile bottom bar): isMobile is width < 640 (useViewport.ts:124
 *   — not the 768 in useIsMobile's docs), and Layout mounts MobileBottomNav
 *   only when isMobile (Layout.tsx:150). The bar is role=navigation
 *   aria-label "Mobile navigation" with links "Go to <label>"
 *   (MobileBottomNav.tsx:84-122); the More button opens a BottomSheet whose
 *   open content is `mobile-nav-more-menu` and whose items are buttons
 *   `mobile-nav-item-<id>` (:145-186). BottomSheet wraps everything in
 *   AnimatePresence {isOpen && …} (BottomSheet.tsx:186-188), so closing
 *   UNMOUNTS it — toHaveCount(0) is real, and handleNavigate closes the sheet
 *   as it navigates (MobileBottomNav.tsx:58-63).
 * - Clause 4b (slide-out menu) meets a DEFECT, and this spec measures it at
 *   both widths instead of pretending: Layout gates the Sidebar itself behind
 *   !isMobile (Layout.tsx:93) while the hamburger that opens the slide-out is
 *   hidden by CSS only at ≥768 (Header.tsx md:hidden), and the drawer's own
 *   translate lives INSIDE Sidebar (the ternary at :267). At 375 the hamburger therefore
 *   toggles state and the backdrop (Layout :95-104, `mobile-overlay`) appears
 *   over an UNMOUNTED drawer — nothing slides out. At 700 the drawer exists
 *   and slides. The two mobile halves are never both true at one width. The
 *   slide position is asserted as geometry (boundingBox().x off-canvas vs 0)
 *   because the class list carries `md:translate-x-0` UNCONDITIONALLY
 *   (the ternary at :267) — a /translate-x-0/ regex would pass while the drawer was
 *   still off-screen. Ruling 86: the false half is filed in the inventory row
 *   as failure-as-evidence, not asserted vacuously.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
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

/** Width the mouse moves to when it must NOT be hovering the rail. */
const FAR_RIGHT: [number, number] = [1400, 500];

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
}

/** Reload is a document load ⇒ boot wave ⇒ drain first (harness.ts). */
async function drainAndReload(page: import('@playwright/test').Page) {
  await page.waitForTimeout(BOOT_QUIET_MS);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
}

test.describe('golden path: sidebar + mobile navigation @critical', () => {
  test('F-017 (desktop): an item click navigates; group and sidebar collapse are remembered across reload', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);
    // ≥ lg: isDesktop (useViewport.ts:126) is what makes the collapse toggle
    // render at all, and it keeps isTablet — the force-collapse band — false.
    await page.setViewportSize({ width: 1440, height: 900 });
    await openShell(page, h);
    await page.mouse.move(...FAR_RIGHT);

    const sidebar = page.getByTestId('sidebar');
    await expect(sidebar).toHaveClass(/w-64/);
    await expect(sidebar).toHaveAttribute('data-collapsed', 'false');

    // Clause 2: collapse ANALYTICS (defaultExpanded true, not the active
    // route, so the auto-expand effect cannot be the thing under test).
    const analyticsHeader = page.getByTestId('nav-group-header-analytics');
    await expect(analyticsHeader).toHaveAttribute('aria-expanded', 'true');
    await analyticsHeader.click();
    await expect(analyticsHeader).toHaveAttribute('aria-expanded', 'false');
    await expect(page.getByTestId('nav-group-content-analytics')).toHaveClass(/max-h-0/);
    await page.mouse.move(...FAR_RIGHT);
    const jar = await page.evaluate(() => localStorage.getItem('sidebar-expansion-state'));
    expect(jar ? JSON.parse(jar).analytics : undefined).toBe(false);

    // Clause 1: a NavLink click navigates client-side (SPA, no boot wave).
    await page
      .getByTestId('nav-group-content-monitoring')
      .getByRole('link', { name: 'Timeline' })
      .click();
    await expect(page).toHaveURL(`${h.ui}/timeline`);

    // Remembered = survives a RELOAD (mount initializer re-reads the jar).
    await drainAndReload(page);
    await page.mouse.move(...FAR_RIGHT);
    await expect(page.getByTestId('nav-group-header-analytics')).toHaveAttribute(
      'aria-expanded',
      'false'
    );

    // Clause 3: the desktop collapse control. The pointer is left inside the
    // rail by the click, and a collapsed rail expands on hover (:271), so the
    // first truth read is the jar, then the pointer leaves and the rendered
    // width follows the state.
    await page.getByTestId('collapse-sidebar-button').click();
    expect(await page.evaluate(() => localStorage.getItem('sidebar-collapsed-state'))).toBe(
      'true' // the 4-char string: saveCollapsedState stores JSON.stringify(true) (:179-185)
    );
    await page.mouse.move(...FAR_RIGHT);
    await expect(sidebar).toHaveAttribute('data-collapsed', 'true');
    await expect(sidebar).toHaveClass(/w-16/);

    // And it is the RESTORED state after a reload, not a hover artifact:
    // fresh mount has isHovered false, so the class is the jar's verdict.
    await drainAndReload(page);
    await page.mouse.move(...FAR_RIGHT);
    await expect(sidebar).toHaveAttribute('data-collapsed', 'true');
    await expect(sidebar).toHaveClass(/w-16/);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test.describe('phone viewport (width < 640 ⇒ isMobile)', () => {
    test.use({ viewport: { width: 375, height: 812 } });

    test('F-017 (phone): the bottom bar and More sheet work; the slide-out is unmounted there (measured)', async ({
      page,
    }) => {
      test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
      if (!harness.ready) return;
      const h = harness;
      test.setTimeout(120_000);
      await openShell(page, h);

      // Layout.tsx:93 — no Sidebar at all below 640; :150 — the bottom bar
      // instead. Both halves of the row's mobile clause in one assertion pair.
      await expect(page.getByTestId('sidebar')).toHaveCount(0);
      const bar = page.getByRole('navigation', { name: 'Mobile navigation' });
      await expect(bar).toBeVisible();

      await bar.getByRole('link', { name: 'Go to Timeline' }).click();
      await expect(page).toHaveURL(`${h.ui}/timeline`);

      // The More sheet: groups × non-primary items, closing as it navigates
      // (MobileBottomNav.tsx:58-63). Entities is monitoring's non-primary
      // item (primaryNavIds = dashboard/timeline/alerts, :32-38).
      await page.getByTestId('mobile-nav-more-button').click();
      const sheet = page.getByTestId('mobile-nav-more-menu');
      await expect(sheet).toBeVisible();
      await expect(page.getByTestId('mobile-nav-group-monitoring')).toBeVisible();
      await page.getByTestId('mobile-nav-item-entities').click();
      await expect(page).toHaveURL(`${h.ui}/entities`);
      await expect(sheet).toHaveCount(0); // AnimatePresence unmounts on close

      // THE DEFECT, measured at phone width: the hamburger is visible (its
      // CSS hiding is md:hidden = ≥768), clicking it flips the shared state
      // and Layout's backdrop renders — but the drawer it is supposed to
      // reveal is not in the DOM, so nothing slides out.
      await page.getByTestId('hamburger-menu').click();
      await expect(page.getByTestId('mobile-overlay')).toBeVisible();
      await expect(page.getByTestId('sidebar')).toHaveCount(0);
      await page.getByTestId('mobile-overlay').click();
      await expect(page.getByTestId('mobile-overlay')).toHaveCount(0);

      // The same control WORKS one band up: at 700, isMobile is false ⇒ the
      // Sidebar (and its drawer) mounts, and md:hidden has not hidden the
      // hamburger. Geometry, not class names: off-canvas then flush.
      await page.setViewportSize({ width: 700, height: 800 });
      const drawer = page.getByTestId('sidebar');
      await expect(drawer).toHaveCount(1);
      const closedBox = await drawer.boundingBox();
      expect(closedBox, 'drawer has no box at 700px').not.toBeNull();
      expect(closedBox!.x).toBeLessThan(0); // -translate-x-full ⇒ off-canvas
      await page.getByTestId('hamburger-menu').click();
      await expect
        .poll(async () => (await drawer.boundingBox())?.x ?? null, {
          timeout: 10_000,
          message: 'the drawer never slid to flush-left at 700px',
        })
        .toBe(0);
      await expect(page.getByTestId('mobile-overlay')).toBeVisible();

      expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
    });
  });
});
