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
 *   (:262), with onMouseEnter setting isHovered whenever isCollapsed (:301).
 *   So (a) between 640 and 1023 the rail is FORCE-collapsed no matter what
 *   the user chose (isTablet, useViewport.ts:125) — the desktop-only toggle
 *   (:318) cannot even render there — and (b) at desktop width, clicking the
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
 *   only when isMobile (Layout.tsx:183). The bar is role=navigation
 *   aria-label "Mobile navigation" with links "Go to <label>"
 *   (MobileBottomNav.tsx:84-122); the More button opens a BottomSheet whose
 *   open content is `mobile-nav-more-menu` and whose items are buttons
 *   `mobile-nav-item-<id>` (:145-186). BottomSheet wraps everything in
 *   AnimatePresence {isOpen && …} (BottomSheet.tsx:186-188), so closing
 *   UNMOUNTS it — toHaveCount(0) is real, and handleNavigate closes the sheet
 *   as it navigates (MobileBottomNav.tsx:58-63).
 * - Clause 4b (slide-out menu) met a DEFECT that [r130f] fixed, and this leg
 *   still measures GEOMETRY for the reason the defect was invisible to class
 *   checks: the aside's class list carries `md:translate-x-0` UNCONDITIONALLY
 *   (Sidebar.tsx, the translate ternary), so a /translate-x-0/ regex passes
 *   while the drawer is still off-screen — boundingBox().x (off-canvas vs 0) is
 *   the only honest read of "slid out". The defect was that Layout.tsx gated the
 *   Sidebar's MOUNT behind !isMobile (width < 640) while the hamburger that
 *   OPENS the drawer is hidden by CSS at `md` (≥768), and the drawer's translate
 *   lives inside Sidebar — so at 375 the hamburger toggled state and the backdrop
 *   (`mobile-overlay`) appeared over an UNMOUNTED drawer. The two mobile halves
 *   could never both be true at one width. The fix removes the mount gate, so
 *   THIS LEG NOW ASSERTS BOTH HALVES AT 375: the bottom bar navigates AND the
 *   hamburger slides the drawer to flush-left.
 * - Always-mounted has a consequence this leg pins too, because it is the part a
 *   screenshot cannot see: below `md` the drawer is hidden by a TRANSFORM, and a
 *   transform does not remove an element from the sequential focus order. Measured
 *   before the `inert` gate existed: 34 tabbable links behind the backdrop,
 *   `close-menu-button` at Tab stop #5 (WCAG 2.4.3). So the closed drawer is
 *   asserted inert AND non-focusable (`link.focus()` is a no-op, and a 10-stop Tab
 *   walk has no `SIDEBAR:` stop), and the OPEN drawer is asserted focusable in the
 *   same leg — without that second half the inert assertions could pass on a
 *   drawer that was unreachable for some unrelated reason.
 *   `toHaveJSProperty('inert', …)` is used rather than `toHaveAttribute` because
 *   React renders `inert={true}` as the EMPTY STRING (measured: getAttribute → ''),
 *   so an attribute-value assert would be a test of React's serialization.
 *   Not covered, deliberately: whether the closed drawer leaves the a11y TREE
 *   (Chromium's ariaSnapshot enumerates all 80 lines inert or not, so no claim),
 *   and where focus lands after the drawer is closed by backdrop or button
 *   (measured: <body>, and the next Tab resumes FORWARD from the drawer's DOM
 *   position rather than at the top of the page — the app's modals behave the same
 *   way, see the F-018 row; the drawer also has no Escape-to-close at all).
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

/**
 * Does the browser ACCEPT focus for the drawer's Timeline link right now?
 *
 * Raw `el.focus()` inside the page rather than `locator.focus()`, and raw
 * `document.activeElement` rather than `toBeFocused()`, for one reason: a closed
 * drawer sits at x = -256, so Playwright's actionability ("element receives
 * events") would time out before it ever asked the question — and a timeout is
 * not evidence about focusability. The return value distinguishes the three
 * states a reader might otherwise conflate: the link is not even in the DOM
 * ('absent'), it is there but the browser refuses focus ('refused'), or focus
 * landed ('focused').
 */
async function timelineAcceptsFocus(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const link = [...document.querySelectorAll('[data-testid="sidebar"] a')].find((a) =>
      a.textContent?.includes('Timeline')
    );
    if (!link) return 'absent';
    (document.activeElement as HTMLElement | null)?.blur?.();
    // The selector ends in ` a`, so this element is an anchor; DOM's declared
    // type is the looser Element, which is why [r149e]'s golden type-check job
    // flagged the bare `.focus()` call (TS2339). A wrong cast here would be
    // invisible to the test, so the selector that justifies it is on this line.
    (link as HTMLElement).focus();
    return document.activeElement === link ? 'focused' : 'refused';
  });
}

/**
 * Press Tab N times from wherever focus sits (callers blur first to start from
 * the top of the document) and name each stop, tagging the ones that landed
 * inside the drawer.
 *
 * This is the instrument the WCAG 2.4.3 claim is actually about — sequential
 * focus order — and it is run in BOTH drawer states on purpose: an assert that
 * only ever expects "no SIDEBAR stop" cannot tell `inert` working from the
 * drawer being unreachable for some unrelated reason (e.g. unmounted, which is
 * exactly what the pre-fix code did).
 */
async function tabWalkStops(page: import('@playwright/test').Page, n: number) {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
  const stops: string[] = [];
  for (let i = 0; i < n; i++) {
    await page.keyboard.press('Tab');
    stops.push(
      await page.evaluate(() => {
        // `activeElement` is nullable and the DOM type says so; the old code
        // assumed non-null and [r149e]'s type-check job flagged all three
        // dereferences (TS18047). Rather than cast, the walk names the state it
        // would otherwise have crashed on — a null activeElement is a real
        // focus outcome worth seeing in the arrow-chain, and the callers below
        // only filter this list for a 'SIDEBAR:' prefix and join it into a
        // message, so the extra token cannot change a passing run's verdict.
        const a = document.activeElement;
        if (!a) return 'NO-FOCUS';
        return (
          (a.closest('[data-testid="sidebar"]') ? 'SIDEBAR:' : '') +
          (a.getAttribute('data-testid') || a.tagName.toLowerCase())
        );
      })
    );
  }
  return stops;
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
    // rail by the click, and a collapsed rail expands on hover (:301), so the
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

    test('F-017 (phone): bottom bar AND slide-out work at the same width; the closed drawer is unreachable to the keyboard', async ({
      page,
    }) => {
      test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
      if (!harness.ready) return;
      const h = harness;
      test.setTimeout(120_000);
      await openShell(page, h);

      const sidebar = page.getByTestId('sidebar');
      const bar = page.getByRole('navigation', { name: 'Mobile navigation' });

      // BOTH halves of the row's mobile clause, at ONE width. Before [r130f] the
      // first line below read toHaveCount(0): Layout unmounted the Sidebar below
      // 640, so the drawer this width's hamburger opens did not exist.
      await expect(sidebar).toHaveCount(1);
      await expect(bar).toBeVisible();

      // Half one: the bottom bar navigates.
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

      // Half two, THE FIX: the same hamburger at the SAME 375 now slides a real
      // drawer to flush-left. Geometry, never the class list (see header).
      // Keyboard activation for the reason the 700px leg below documents — the
      // aside's own onClick fires on mousedown and the sliding drawer passes
      // under a stationary pointer, so click()'s second hit-test at mouseup
      // loses on a slow runner.
      const closedBox = await sidebar.boundingBox();
      expect(closedBox, 'drawer has no box at 375px').not.toBeNull();
      expect(closedBox!.x, 'the drawer starts on-canvas at 375px').toBeLessThan(0);

      // THE CONSEQUENCE OF ALWAYS-MOUNTED, pinned: hidden by a TRANSFORM is not
      // hidden to a keyboard. Measured before the inert gate existed: 34 tabbable
      // links behind the backdrop and `close-menu-button` at Tab stop #5, i.e. a
      // WCAG 2.4.3 break. Note what is NOT used here: Playwright 1.63's actionability
      // has no `inert` support (grep of playwright-core finds the word only in its
      // bundled viewers), so `toBeEnabled()` on a link inside an inert subtree is
      // near-vacuous — it checks `:disabled`, which an <a> never matches. The
      // attribute, programmatic focus, and the Tab walk are the three instruments
      // that can each fail.
      await expect(sidebar).toHaveJSProperty('inert', true);
      expect(await timelineAcceptsFocus(page), 'a closed drawer accepts focus').toBe('refused');
      const closedStops = await tabWalkStops(page, 10);
      expect(
        closedStops.filter((s) => s.startsWith('SIDEBAR:')),
        `a closed drawer is tabbable: ${closedStops.join(' → ')}`
      ).toEqual([]);

      await page.getByTestId('hamburger-menu').press('Enter');
      await expect
        .poll(async () => (await sidebar.boundingBox())?.x ?? null, {
          timeout: 10_000,
          message: 'the drawer never slid to flush-left at 375px',
        })
        .toBe(0);
      await expect(page.getByTestId('mobile-overlay')).toBeVisible();

      // ...and OPEN means reachable, which is what stops the three asserts above
      // from passing on a drawer that is unreachable for some unrelated reason.
      await expect(sidebar).toHaveJSProperty('inert', false);
      expect(await timelineAcceptsFocus(page), 'an open drawer refuses focus').toBe('focused');
      const openStops = await tabWalkStops(page, 8);
      expect(
        openStops.filter((s) => s.startsWith('SIDEBAR:')).length,
        `an open drawer is not tabbable: ${openStops.join(' → ')}`
      ).toBeGreaterThan(0);
      await sidebar.getByRole('button', { name: 'Close menu' }).click();
      await expect
        .poll(async () => (await sidebar.boundingBox())?.x ?? null, {
          timeout: 10_000,
          message: 'the drawer never slid back off-canvas',
        })
        .toBeLessThan(0);
      await expect(sidebar).toHaveJSProperty('inert', true);

      // The backdrop closes it too — but the tap must land on the EXPOSED strip,
      // not the element's centre: the overlay is fixed inset-0 (full 375 width)
      // while the open drawer occupies x 0–256 at z-40 over it (overlay z-30), so
      // the centre Playwright aims at is the drawer. This is a NEW property of
      // always-mounted: with the drawer unmounted at 375 the centre was free.
      await page.getByTestId('hamburger-menu').press('Enter');
      await expect
        .poll(async () => (await sidebar.boundingBox())?.x ?? null, { timeout: 10_000 })
        .toBe(0);
      await page.getByTestId('mobile-overlay').click({ position: { x: 340, y: 400 } });
      await expect(page.getByTestId('mobile-overlay')).toHaveCount(0);
      // Fully shut before the next leg: Layout's backdrop cleared the flag, but
      // the aside is transition-all duration-300 and fixed inset-y-0 (full
      // height), so a still-sliding drawer covers the hamburger's hit point.
      await page.waitForTimeout(600);

      // One band up (700) the clause is unchanged by the fix: isMobile is FALSE
      // there yet the drawer still works, because `md` (768) — not `isMobile` —
      // governs the drawer. This is also the leg that would catch an `inert`
      // keyed on isMobile: at 700 the drawer is off-canvas while closed (so inert)
      // and must become reachable the moment it is open.
      await page.setViewportSize({ width: 700, height: 800 });
      await expect(sidebar).toHaveCount(1);
      const wideClosedBox = await sidebar.boundingBox();
      expect(wideClosedBox, 'drawer has no box at 700px').not.toBeNull();
      expect(wideClosedBox!.x).toBeLessThan(0); // -translate-x-full ⇒ off-canvas
      await expect(sidebar).toHaveJSProperty('inert', true);
      // Keyboard activation, deliberately: React's onClick fires on KEYDOWN,
      // click() fires on MOUSEUP — and Playwright hit-tests the pointer AGAIN
      // at mouseup (actionability check, after the click() call itself). The
      // aside's onClick at Layout.tsx:68 flips the flag on mousedown; while it
      // slides in (duration-300) its left edge passes under the stationary
      // pointer and the close button (Sidebar.tsx:306-314, in the md:hidden
      // header, ~354px x on a 700px viewport) covers the hamburger's hit
      // point. Locally the mouseup wins the race and lands on the hamburger;
      // on CI's runner it consistently landed on the sliding aside — "the
      // close-menu-button ... intercepts pointer events" × 3 attempts
      // (junit, run 38146684985). A keyboard event has no second hit-test to
      // lose; the poll below proves the open itself.
      await page.getByTestId('hamburger-menu').press('Enter');
      await expect
        .poll(async () => (await sidebar.boundingBox())?.x ?? null, {
          timeout: 10_000,
          message: 'the drawer never slid to flush-left at 700px',
        })
        .toBe(0);
      await expect(page.getByTestId('mobile-overlay')).toBeVisible();
      // Instrument note: at 700 the drawer is isTablet ⇒ FORCE-collapsed
      // (Sidebar.tsx isCollapsed), so it renders w-16 with ICON-ONLY links. The
      // link is still in the DOM and its text content is unchanged, so
      // timelineAcceptsFocus (which matches on textContent, not accessible name)
      // still finds it — but getByRole would not, which is why the focus probe is
      // a DOM probe.
      await expect(sidebar).toHaveJSProperty('inert', false);
      expect(await timelineAcceptsFocus(page), 'an open drawer refuses focus at 700px').toBe(
        'focused'
      );

      expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
    });
  });
});
