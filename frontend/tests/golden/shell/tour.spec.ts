/**
 * FE-1 golden path (F2.3): F-021 product tour (first visit).
 *
 * Row claim: "on first visit a 7-step guided tour runs; Skip/Finish stores
 * completion". Client-only: react-joyride + localStorage keys
 * nemotron-tour-completed / nemotron-tour-skipped (src/config/tourSteps.ts:15,
 * :20 — RAW 'true' strings written by markTourCompleted/markTourSkipped :48-65,
 * read by shouldShowTour :91-93; unlike F-020's theme/settings keys these are
 * NOT JSON-stringified — tourSteps.ts writes the literal itself).
 *
 * Mount (App.tsx:342): <ProductTour /> sits INSIDE BrowserRouter but OUTSIDE
 * <Routes> and OUTSIDE ProtectedRoute — it boots on EVERY route document,
 * /login included (shell/harness.ts seedTourDismissed records exactly this
 * collision being measured on this stack; other shell specs seed the jar to
 * escape it — this spec is the row that OWNS it).
 *
 * Three of the seven steps target selectors nothing renders (inventory note,
 * verified against src this turn): the ONLY data-tour writer is
 * Sidebar.tsx:74/:140 (item.dataTour), and sidebarNav.ts supplies only
 * 'timeline-link' (:71) and 'settings-link' (:150) — while tourSteps.ts:115
 * targets [data-tour="risk-gauge"], :124 "camera-grid", :133 "activity-feed".
 *
 * What the shipped library does with a missing target is NOT what the
 * inventory note assumes. The vendored source (react-joyride 2.9.3,
 * dist/index.js) kills its own auto-advance — TARGET_NOT_FOUND skips forward
 * only `if (!controlled)` (:1844-1849), and controlled is `is.number(stepIndex)`
 * (:933), which ProductTour.tsx:204 always satisfies — so neither the note's
 * "skips a missing target, so the tour runs short" nor the freeze the
 * controlled reading predicts is the whole story. MEASURED 2026-10-11 on the
 * live stack (this spec's dead-targets test): step 1's Next into the dead
 * [data-tour="risk-gauge"] makes overlay, tooltip and every joyride button
 * ALL vanish at once, and NOTHING is stored — so every fresh document boots
 * the same tour back at step 1 (the first-visit loop the same test pins).
 * Joyride's own `console.warn("Target not mounted")` (dist :1841) is the
 * console fingerprint the test polls for.
 *
 * Skip/close semantics the spec pins from ProductTour.tsx (its own code, not
 * the library's): ACTIONS.CLOSE (:166-171 — the X button, Esc
 * [disableCloseOnEsc=false :210] or the overlay click [disableOverlayClose is
 * false :211]) calls markTourCompleted() IMMEDIATELY (the NEM-3518 branch — a
 * close stores COMPLETION, not skip); the Skip button (showSkipButton :209,
 * locale skip 'Skip Tour' :219) → STATUS.SKIPPED → markTourSkipped (:180-184),
 * leaving nemotron-tour-completed untouched. Footer skip renders only
 * `showSkipButton && !isLastStep` (dist :1566) — visible on step 1 of 7.
 *
 * Every navigation goes through a BOOT_QUIET_MS drain (harness.ts): the SPA's
 * API calls ride the frontend container's nginx /api throttle, and this file
 * adds up to two boots per test (first visit + the no-return reload).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { BOOT_QUIET_MS, closedByGuard, readShellHarness, type ShellHarness } from './harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/**
 * Why this spec takes the `context` fixture instead of `page`:
 *
 * guard.ts:102-115 — the golden project's PAGE fixture — seeds
 * nemotron-tour-completed/-skipped = 'true' via addInitScript so the Joyride
 * overlay never steals clicks from specs whose subject is not the tour (the
 * e2e project does the same via config storageState, playwright.config.ts:162,
 * and shell/harness.ts seedTourDismissed replays it per spec). For F-021 the
 * overlay IS the subject. The seed cannot be undone after the fact — and it is
 * context-wide once registered: measured 2026-10-11, a page spawned later via
 * context.newPage() in the same test booted with jar {completed:'true',
 * skipped:'true'} too, while the same app under a bare Playwright context
 * boots the tour overlay over a virgin jar (.r55-probes/tour-isolate.mjs).
 *
 * Playwright instantiates fixtures LAZILY: a test that requests only
 * `{ context }` never runs the seeding `page` fixture. The context fixture
 * (guard.ts:98-100) just arms the guard, and the guard's own
 * context.newPage wrapper (:62-67) arms every page it spawns — so pages born
 * here ride the full interception (guard-contract.spec.ts: "the context
 * fixture arms on its own, with no page fixture") WITHOUT the seed: the first
 * visit is real because nothing stored anything, not because a script faked
 * an empty jar. No harness file is touched (ruling 87); closedByGuard at each
 * test's tail is the tripwire that the tour page is guard-armed.
 */
async function openFirstVisit(
  context: import('@playwright/test').BrowserContext,
  h: ShellHarness,
  path = '/'
): Promise<import('@playwright/test').Page> {
  const tour = await context.newPage(); // guard-armed spawn, seedless context
  tour.on('console', (m) => {
    if (/target|tour|joyride/i.test(m.text()))
      console.log('TOUR-CONSOLE:', m.type(), m.text().slice(0, 240));
  });
  await tour.waitForTimeout(BOOT_QUIET_MS); // shared nginx burst, harness.ts
  await tour.goto(h.ui + path, { waitUntil: 'domcontentloaded' });
  return tour;
}

/** Raw jar snapshot (tourSteps writes literals; parse nothing). */
const jar = (page: import('@playwright/test').Page) =>
  page.evaluate(() => ({
    completed: localStorage.getItem('nemotron-tour-completed'),
    skipped: localStorage.getItem('nemotron-tour-skipped'),
  }));

const tourRoot = (page: import('@playwright/test').Page) =>
  page.locator('div[data-test-id="overlay"], .react-joyride__overlay');

test.describe('golden path: first-visit product tour @critical', () => {
  test.setTimeout(90_000);

  test('F-021 (welcome): a virgin jar boots the tour over the dashboard, with the welcome step, progress and Skip', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    // auth gate is down on this stack (setup-status auth_required=false,
    // F1.3) so an unauthenticated first visit lands straight on the
    // dashboard — the tour mount (App.tsx:342) does not care about auth.
    const tour = await openFirstVisit(context, h);

    // The jar really is virgin here — the row's "first visit" precondition.
    expect(await jar(tour)).toEqual({ completed: null, skipped: null });

    // The overlay + the welcome tooltip (step 1 targets 'body', placement
    // center, title "Welcome to Nemotron Security" — tourSteps.ts:105-113).
    await expect(tourRoot(tour)).toBeVisible({ timeout: 20_000 });
    await expect(tour.getByText('Welcome to Nemotron Security')).toBeVisible();
    await expect(tour.getByRole('button', { name: 'Skip Tour' })).toBeVisible();
    await expect(tour.getByRole('button', { name: 'Next' })).toBeVisible();
    // The tour is an overlay, not a route: the app behind it is the dashboard.
    await expect(tour.getByTestId('header-branding')).toBeAttached();

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });

  test('F-021 (dead targets): Next into the missing [data-tour="risk-gauge"] deletes the entire tour UI, stores nothing, and the same dead tour returns on every reload', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const tour = await openFirstVisit(context, h);
    await expect(tour.getByRole('button', { name: 'Next' })).toBeVisible({ timeout: 20_000 });

    // Step 2 targets [data-tour="risk-gauge"] — nothing in src renders it
    // (only Sidebar.tsx:74/:140 writes data-tour; sidebarNav supplies just
    // timeline-link/settings-link). Confirm the target is absent app-wide:
    await expect(tour.locator('[data-tour="risk-gauge"]')).toHaveCount(0);

    const consoleLines: string[] = [];
    tour.on('console', (m) => consoleLines.push(m.text()));

    await tour.getByRole('button', { name: 'Next' }).click();

    // Joyride's OWN warning that step 2's target never mounted (dist/index.js
    // :1841 console.warn) — the app's instrument, not our opinion:
    await expect
      .poll(() => consoleLines.some((w) => /Target not mounted/.test(w)), { timeout: 5_000 })
      .toBe(true);

    // MEASURED 2026-10-11 (probe run on the live stack), user-visible shape of
    // the dead step — neither the inventory note's assumption ("Joyride skips a
    // missing target, so the tour runs short") nor the controlled-mode freeze
    // the library reading suggested: the ENTIRE tour UI disappears. Overlay,
    // tooltip and every joyride button all go to zero and stay gone.
    await expect(tour.locator('.react-joyride__overlay')).toHaveCount(0);
    await expect(tour.locator('.__react_component_tooltip')).toHaveCount(0);
    await expect(tour.locator('.react-joyride button')).toHaveCount(0);
    await tour.waitForTimeout(3_000); // stays gone — not a transition frame
    await expect(tour.locator('.react-joyride__overlay')).toHaveCount(0);

    // And NOTHING was stored. That emptiness is what makes the next leg the
    // row's real defect: from the vanished state no Skip/Finish is clickable,
    // the jar stays virgin, and shouldShowTour (:91-93) therefore stays true.
    // (Deliberately NO Esc between the two legs — ACTIONS.CLOSE stores
    // completed immediately (:166-171), which would break the jar-empty
    // precondition the reload leg rides. Whether the vanished tour still
    // answers Esc is unmeasured and not what the row turns on.)
    expect(await jar(tour)).toEqual({ completed: null, skipped: null });

    // The first-visit loop, pinned: a fresh document boots the SAME tour back
    // at step 1 (ProductTour remounts with useState(startIndex=0) :127).
    await tour.waitForTimeout(BOOT_QUIET_MS);
    await tour.reload({ waitUntil: 'domcontentloaded' });
    await expect(tour.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(tourRoot(tour)).toBeVisible({ timeout: 20_000 });
    await expect(tour.getByText('Welcome to Nemotron Security')).toBeVisible();

    // The escape hatch that DOES ship: only a fresh welcome step's Skip ends
    // it (the next test pins the storage that follows) — the user gets out of
    // the loop by skipping, never by finishing.
    await tour.getByRole('button', { name: 'Skip Tour' }).click();
    await expect(tourRoot(tour)).toBeHidden({ timeout: 5_000 });

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });

  test('F-021 (skip): Skip Tour stores skipped-only and the tour never returns on reload', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const tour = await openFirstVisit(context, h);
    await expect(tour.getByRole('button', { name: 'Skip Tour' })).toBeVisible({ timeout: 20_000 });

    await tour.getByRole('button', { name: 'Skip Tour' }).click();
    await expect(tourRoot(tour)).toBeHidden({ timeout: 5_000 });
    // ProductTour.tsx:180-184: SKIPPED marks skipped, NOT completed.
    expect(await jar(tour)).toEqual({ completed: null, skipped: 'true' });

    // First-visit means once: a reload boots the app with the stored jar and
    // the tour must NOT run again (shouldShowTour :91-93 false; the component
    // renders null :196-198 — no joyride DOM at all). Lone boot → drain first.
    await tour.waitForTimeout(BOOT_QUIET_MS);
    await tour.reload({ waitUntil: 'domcontentloaded' });
    await expect(tour.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(tour.locator('.react-joyride__overlay')).toHaveCount(0);

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });

  test('F-021 (close stores completion): Esc mid-tour writes completed immediately (NEM-3518 branch) and the tour never returns', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const tour = await openFirstVisit(context, h);
    await expect(tourRoot(tour)).toBeVisible({ timeout: 20_000 });

    await tour.keyboard.press('Escape');
    await expect(tourRoot(tour)).toBeHidden({ timeout: 5_000 });
    // ACTIONS.CLOSE at ProductTour.tsx:166-171 marks COMPLETED (not skipped).
    expect(await jar(tour)).toEqual({ completed: 'true', skipped: null });

    await tour.waitForTimeout(BOOT_QUIET_MS);
    await tour.reload({ waitUntil: 'domcontentloaded' });
    await expect(tour.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(tour.locator('.react-joyride__overlay')).toHaveCount(0);

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });
});
