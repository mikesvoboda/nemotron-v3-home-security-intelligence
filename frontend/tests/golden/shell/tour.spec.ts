/**
 * F-021 golden path: the first-visit product tour is completable.
 *
 * Row claim: "on first visit a 7-step guided tour runs; Skip/Finish stores
 * completion". Client-only: react-joyride + localStorage keys
 * nemotron-tour-completed / nemotron-tour-skipped (src/config/tourSteps.ts:15,
 * :20 — RAW 'true' strings written by markTourCompleted/markTourSkipped :48-65,
 * read by shouldShowTour :91-93; unlike F-020's theme/settings keys these are
 * NOT JSON-stringified — tourSteps.ts writes the literal itself).
 *
 * ── What this spec used to pin, and why it no longer does ───────────────────
 * FE-1 wrote this file (F2.3 batch, commit 8f87050d7) against the SHIPPED
 * defect and demoted the row to `half-built`. Three of the seven steps targeted
 * selectors nothing rendered: [data-tour="risk-gauge"] had no writer at all, and
 * camera-grid/activity-feed had none either (the only data-tour writer was
 * Sidebar.tsx:74/:140, and sidebarNav.ts supplies just 'timeline-link' and
 * 'settings-link'). [r130f] fixes that; per ruling 130 the golden is FLIPPED
 * from pinning the break to asserting the fix, so the dead-target leg is gone
 * and what replaces it measures the fixed behaviour.
 *
 * FE-1's measurement is still the reason the fix had to be more than cosmetic,
 * and it is worth keeping in words. A dead target does NOT make Joyride "skip
 * short" the way the old inventory note assumed. react-joyride 2.9.3
 * (components/Step.tsx:101-110) warns and fires EVENTS.TARGET_NOT_FOUND, then
 * advances only `if (!controlled)` — and `controlled` is `is.number(stepIndex)`,
 * which ProductTour.tsx:231 always satisfies — so the library never advances.
 * Measured on the live stack, one Next from the welcome into the dead step 2
 * removed the ENTIRE tour UI (overlay, tooltip and every joyride button at 0,
 * still 0 after 3 s) while storing NOTHING, so shouldShowTour stayed true and
 * every fresh document booted the same dead tour back at step 1: a first-visit
 * loop the user could only escape with Skip.
 *
 * ── The two halves of the fix this spec pins ────────────────────────────────
 * (1) WRITERS. All three missing targets now exist: StatsRow's risk card writes
 *     data-tour="risk-card" (StatsRow.tsx:221, beside its risk-card testid) and
 *     the dashboard widget sections write data-tour="camera-grid" /
 *     "activity-feed" (DashboardLayout.tsx:190/:204). Anchoring the latter two on
 *     the widget SECTION is the choice that matters: CameraGrid's own container
 *     is rendered only when cameras exist (it returns `camera-grid-empty` at zero
 *     cameras), so anchoring there would trade a permanently-dead target for a
 *     DATA-dependent one. The section renders whenever the widget is visible,
 *     whatever its data — so THIS stack, which has no cameras configured, still
 *     has every target on the page. Measured before writing this file: an
 *     unauthenticated visit to / on the probe build exposes exactly
 *     [timeline-link, settings-link, risk-card, camera-grid, activity-feed], one
 *     each. That is what the "completes" leg witnesses.
 * (2) RESILIENCE. ProductTour's callback answers TARGET_NOT_FOUND by advancing
 *     itself (:165-177) — what uncontrolled Joyride would have done. The writers
 *     make the default dashboard completable; the branch is what makes it
 *     impossible for ONE missing target to re-create the dead loop, and the
 *     "hidden widget" leg exercises it with real persisted user state.
 *
 * ── The decision harness.ts left to this spec ───────────────────────────────
 * "Whether the tour SHOULD start on the public login page is F-021's row,
 * decided by its own spec." Decision: it stays app-wide. The mount (App.tsx:342)
 * is a SIBLING of <Routes>, outside ProtectedRoute, so it boots on every document
 * including /login, and this row does not move it — the reason is the clause's
 * own logic: the component cannot know which targets the current route will
 * render (a lazy chunk, a hidden widget, a public route), and gating the mount on
 * a route list would be a hand-maintained guess about it. The resilience branch
 * instead makes "starts where its targets are absent" harmless: on /login the
 * dashboard steps auto-skip and the tour ends on its 'body' steps instead of
 * vanishing into a loop. So no step can target an element that never renders
 * AND stall the tour, which is what the clause protects. Whether the tour's copy
 * is worth showing on /login is a design question, not a dead-target bug: it is
 * recorded in the PR's "not covered" note rather than answered by moving the
 * mount, and no test here claims it.
 *
 * ── Which DOM hooks this spec uses, and why not the obvious ones ────────────
 * Verified against node_modules/react-joyride/src, not from memory:
 *  - Every control carries a stable data-test-id (Tooltip/Container.tsx:18-44):
 *    button-primary / button-skip / button-back / button-close, plus
 *    Overlay.tsx:247 data-test-id="overlay". Those are the click anchors.
 *  - The Next button's ACCESSIBLE NAME is not 'Next': getMergedStep merges the
 *    tour-level showProgress into the step (modules/step.ts:26) and the default
 *    locale ships nextLabelWithProgress (defaults.ts:21), so the label is
 *    "Next (Step N of 7)". The spec pins that once — a page-object that matched
 *    /^Next$/ would have been silently wrong, and substring name matching is
 *    what hid it from FE-1's version of this file.
 *  - Step titles are asserted through the tooltip's OWN role and name
 *    (Tooltip/index.tsx:110 sets role="alertdialog" aria-modal, Container.tsx:50
 *    sets aria-label={title}) instead of page-wide getByText, because the app
 *    itself renders the same words — dashboard-config-store.ts:139 names a widget
 *    'Activity Feed' and EventTimeline.tsx:1096 renders an 'Event Timeline' h1. A
 *    page-wide text query would be a strict-mode violation waiting to happen.
 *  - Console warnings are asserted with this distinction (modules/dom.ts:170
 *    isElementVisible trips only on display:none/visibility:hidden up the
 *    ancestor chain): a target that EXISTS but is hidden warns "Target not
 *    visible", a target that is absent warns "Target not mounted". The collapsed
 *    nav groups animate with max-height/opacity, which does NOT trip it, so the
 *    nav steps stay warn-free; a widget hidden by config is unmounted, so the
 *    hidden-widget leg expects "Target not mounted".
 *
 * Skip/close semantics unchanged by the fix, pinned from ProductTour.tsx:
 * ACTIONS.CLOSE (:193-198 — the X button, Esc [disableCloseOnEsc=false :237] or
 * the overlay click [disableOverlayClose false :238]) calls markTourCompleted()
 * IMMEDIATELY (the NEM-3518 branch — a close stores COMPLETION, not skip); the
 * Skip button (showSkipButton :235, locale.skip 'Skip Tour' :246) →
 * STATUS.SKIPPED → markTourSkipped (:207-211), leaving completed untouched.
 * Joyride only renders skip on non-final steps (Container.tsx:26), which the
 * "completes" leg uses as a last-step instrument.
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
 * overlay never steals clicks from specs whose subject is not the tour (the e2e
 * project does the same via config storageState, playwright.config.ts:162, and
 * shell/harness.ts seedTourDismissed replays it per spec). For F-021 the
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
  seed?: { label: string; fn: (value: string) => void; value: string }
): Promise<import('@playwright/test').Page> {
  const tour = await context.newPage(); // guard-armed spawn, seedless context
  tour.on('console', (m) => {
    if (/target|tour|joyride/i.test(m.text()))
      console.log('TOUR-CONSOLE:', m.type(), m.text().slice(0, 240));
  });
  // addInitScript runs before any script of the document, so this is pre-boot
  // user state, not a mid-flight patch. The payload rides Playwright's ARG slot
  // on purpose: addInitScript serializes the function's SOURCE, so a closed-over
  // Node variable (payload) arrives in the browser as an undefined free variable
  // and the script dies silently — measured 2026-10-13, a closure-form seed
  // leaves the widget visible and the leg's own effect assertion goes red.
  // Every leg that seeds ALSO asserts its effect landed (see
  // hiddenDashboardWidget), so a seed that fails can never pass quietly.
  if (seed) await tour.addInitScript(seed.fn, seed.value);
  await tour.waitForTimeout(BOOT_QUIET_MS); // shared nginx burst, harness.ts
  await tour.goto(`${h.ui}/`, { waitUntil: 'domcontentloaded' });
  return tour;
}

/** Raw jar snapshot (tourSteps writes literals; parse nothing). */
const jar = (page: import('@playwright/test').Page) =>
  page.evaluate(() => ({
    completed: localStorage.getItem('nemotron-tour-completed'),
    skipped: localStorage.getItem('nemotron-tour-skipped'),
  }));

/**
 * Joyride's inline render root (components/index.tsx:374, `<div className="react-joyride">`),
 * which ProductTour renders inside #root. It is ONLY a mounted-instrument here:
 * measured 2026-10-13, it is 1 while the tour runs and 0 once the jar is
 * dismissed (ProductTour returns null, so the whole subtree is gone), which is
 * what makes the reload assertions below count-to-zero assertions rather than
 * "selector that never matched anything" assertions.
 *
 * It is NOT an ancestor of the tooltip. Joyride portals each step's tooltip to
 * its own body-level node — measured on the live build, `document.body` children
 * while the tour runs are exactly [div#root, div#react-joyride-step-<index>,
 * div#react-joyride-portal] — so `.locator(...)` under this root finds nothing.
 * An earlier draft of this file made that mistake and the run said so loudly
 * ("element(s) not found" for button-skip), which is the whole reason these
 * portal positions are written down instead of assumed from the JSX.
 */
const joyrideRoot = (page: import('@playwright/test').Page) => page.locator('div.react-joyride');

/** Portaled overlay (Portal id="react-joyride-portal" → Overlay data-test-id). */
const tourOverlay = (page: import('@playwright/test').Page) =>
  page.locator('div[data-test-id="overlay"]');

/**
 * The portaled tooltip element itself (Container.tsx:51 className). The footer
 * controls are its descendants (measured: `.react-joyride__tooltip
 * [data-test-id="button-primary"]` → 1, same selector under div.react-joyride →
 * 0), so this is the scope the click helpers hang off.
 */
const tooltipBox = (page: import('@playwright/test').Page) =>
  page.locator('.react-joyride__tooltip');

/** The tooltip whose title is `title`, by its own accessible role + name. */
const tooltipFor = (page: import('@playwright/test').Page, title: string) =>
  page.getByRole('alertdialog', { name: title, exact: true });

/** Primary footer control: 'Next (Step N of 7)' mid-tour, 'Finish' on step 7. */
const primaryButton = (page: import('@playwright/test').Page) =>
  tooltipBox(page).locator('[data-test-id="button-primary"]');

const skipButton = (page: import('@playwright/test').Page) =>
  tooltipBox(page).locator('[data-test-id="button-skip"]');

/** Console text captured from the moment of the call onward. */
function collectConsole(page: import('@playwright/test').Page): string[] {
  const lines: string[] = [];
  page.on('console', (m) => lines.push(m.text()));
  return lines;
}

/**
 * Persisted dashboard-config-v2 with one widget hidden. This is the shape the
 * app's own zustand persist middleware writes — dashboard-config-store.ts:
 * STORAGE_KEY :104, createJSONStorage(localStorage) :335, version CONFIG_VERSION
 * 2 :336, and partialize :367-373 emits exactly
 * {widgets, theme, refreshInterval, compactMode, version}.
 *
 * Two details that make this a REAL replay rather than a plausible mock:
 *  - `widgets` is the full ordered array straight from DEFAULT_WIDGETS
 *    (:118-160), INCLUDING the three that ship hidden (gpu-stats,
 *    pipeline-telemetry, pipeline-queues, visible:false). Flipping them to true
 *    would add widgets the app's Configure modal never shows by default and
 *    change what the dashboard renders.
 *  - Only the named widget's `visible` flips. `migrate()` (:337-366) re-applies
 *    DEFAULT_WIDGETS names/descriptions and PRESERVES these visibility flags and
 *    this order, so the seed survives migration unchanged — name/description
 *    text here is irrelevant to the outcome, which is why it is terse.
 *
 * A real user produces exactly this state by unticking a widget in the Configure
 * dashboard modal, and can absolutely do it before finishing a first-visit tour.
 */
function hiddenDashboardWidget(hideId: string): {
  label: string;
  fn: (value: string) => void;
  value: string;
} {
  const defaults: Array<[string, boolean]> = [
    ['stats-row', true],
    ['ai-summary-row', true],
    ['camera-grid', true],
    ['activity-feed', true],
    ['gpu-stats', false],
    ['pipeline-telemetry', false],
    ['pipeline-queues', false],
  ];
  const payload = JSON.stringify({
    state: {
      widgets: defaults.map(([id, visible]) => ({
        id,
        name: id,
        description: '',
        visible: id === hideId ? false : visible,
      })),
      theme: 'dark',
      refreshInterval: 0,
      compactMode: false,
      version: 2,
    },
    version: 2,
  });
  return {
    label: hideId,
    // The seed reads its ARGUMENT — see openFirstVisit's note on serialization.
    fn: (value: string) => {
      localStorage.setItem('dashboard-config-v2', value);
    },
    value: payload,
  };
}

/** The 7 step titles, in tourSteps order (tourSteps.ts:105-171). */
const STEP_TITLES = [
  'Welcome to Nemotron Security',
  'Risk Level',
  'Camera Grid',
  'Activity Feed',
  'Event Timeline',
  'Settings',
  'Tour Complete',
] as const;

test.describe('golden path: first-visit product tour @critical', () => {
  test.setTimeout(120_000);

  test('F-021 (welcome): a virgin jar boots the tour over the dashboard, with the welcome step, Skip and a labeled Next', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    // auth gate is down on this stack (setup-status auth_required=false, F1.3)
    // so an unauthenticated first visit lands on the dashboard — the tour mount
    // (App.tsx:342) does not care about auth. Measured: / stays / here.
    const tour = await openFirstVisit(context, h);

    // The jar really is virgin here — the row's "first visit" precondition.
    expect(await jar(tour)).toEqual({ completed: null, skipped: null });

    // Step 1 targets 'body', placement center, title 'Welcome to Nemotron
    // Security'. The tooltip is asserted by role+name, so this cannot be the
    // app's own copy matching by accident.
    await expect(tourOverlay(tour)).toBeVisible({ timeout: 20_000 });
    await expect(tooltipFor(tour, STEP_TITLES[0])).toBeVisible();
    await expect(skipButton(tour)).toBeVisible();
    await expect(primaryButton(tour)).toBeVisible();
    // The label this spec refuses to assert by /^Next$/ — see the header note.
    await expect(primaryButton(tour)).toHaveAccessibleName('Next (Step 1 of 7)');
    // The tour is an overlay, not a route: the app behind it is the dashboard.
    await expect(tour.getByTestId('header-branding')).toBeAttached();

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });

  test('F-021 (completes): all 7 targets render on a camera-less stack and Finish stores completion', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const tour = await openFirstVisit(context, h);
    await expect(primaryButton(tour)).toBeVisible({ timeout: 20_000 });

    // Steps 2-6 point at DASHBOARD chrome, which the lazy route mounts after its
    // data lands (DashboardPage returns a skeleton, not the layout, until then),
    // so target counts are only meaningful once the real layout is up. Wait for
    // the app's own signal rather than a longer timeout.
    await expect(tour.getByTestId('dashboard-layout')).toBeVisible({ timeout: 30_000 });

    // The row's clause, witnessed positively instead of as an absence: each
    // formerly-dead selector now has EXACTLY ONE writer on the page. camera-grid
    // is here on a stack with NO cameras because the anchor is the widget
    // SECTION, not CameraGrid's own container.
    await expect(tour.locator('[data-tour="risk-card"]')).toHaveCount(1);
    await expect(tour.locator('[data-tour="camera-grid"]')).toHaveCount(1);
    await expect(tour.locator('[data-tour="activity-feed"]')).toHaveCount(1);
    // And the dead selector FE-1 measured is not merely unreached, it is gone.
    await expect(tour.locator('[data-tour="risk-gauge"]')).toHaveCount(0);

    const noise = collectConsole(tour);

    // Walk the whole tour. Asserting each title's tooltip became visible BEFORE
    // clicking Next is what proves the step actually displayed — a tour that
    // silently skipped a dead step would still reach 'Tour Complete'.
    for (const [i, title] of STEP_TITLES.entries()) {
      await expect(tooltipFor(tour, title)).toBeVisible({ timeout: 10_000 });
      if (i === STEP_TITLES.length - 1) break;
      // Skip is rendered on every step EXCEPT the last (Container.tsx:26), so
      // its disappearance is the independent instrument for "this is step 7".
      await expect(skipButton(tour)).toBeVisible();
      await primaryButton(tour).click();
    }
    await expect(skipButton(tour)).toHaveCount(0);
    await expect(primaryButton(tour)).toHaveAccessibleName('Finish');

    // Joyride's complaint about an unmounted target never fired. This is the
    // app's instrument, not our opinion: FE-1's dead-target leg polled for this
    // same string to PROVE the break, so its absence here is the same witness
    // read the other way. ('not visible' is covered too: a step whose target
    // exists but is display:none rides the same event.)
    expect(noise.filter((w) => /Target not mounted|Target not visible/.test(w))).toEqual([]);

    // Finishing is the row's other half, and it is the state FE-1 recorded as
    // unreachable in the shipped UI. STATUS.FINISHED → markTourCompleted, and
    // completed is NOT skipped (ProductTour.tsx:201-206).
    await primaryButton(tour).click();
    await expect(tourOverlay(tour)).toBeHidden({ timeout: 5_000 });
    expect(await jar(tour)).toEqual({ completed: 'true', skipped: null });

    // First-visit means once: reload with the stored jar and no joyride DOM at
    // all (ProductTour returns null, :223-225, so even the root div is absent).
    await tour.waitForTimeout(BOOT_QUIET_MS);
    await tour.reload({ waitUntil: 'domcontentloaded' });
    await expect(tour.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(joyrideRoot(tour)).toHaveCount(0);

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });

  test('F-021 (a hidden widget cannot kill the tour): a widget the user unticked is skipped past, not fatal', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const tour = await openFirstVisit(context, h, hiddenDashboardWidget('camera-grid'));

    // The seed landed, or this leg proves nothing: DashboardLayout renders a
    // widget's section only when it is visible, so the section and its anchor are
    // both genuinely gone.
    await expect(tour.getByTestId('dashboard-layout')).toBeVisible({ timeout: 30_000 });
    await expect(tour.getByTestId('widget-camera-grid')).toHaveCount(0);
    await expect(tour.locator('[data-tour="camera-grid"]')).toHaveCount(0);
    // The neighbours survive, so this is one hidden widget, not a dead dashboard.
    await expect(tour.getByTestId('widget-activity-feed')).toHaveCount(1);

    // Step 3 therefore targets an element that never renders — the exact
    // condition the row names, produced by a user action instead of a bug.
    await expect(primaryButton(tour)).toBeVisible({ timeout: 20_000 });
    const noise = collectConsole(tour);

    await expect(tooltipFor(tour, STEP_TITLES[0])).toBeVisible();
    await primaryButton(tour).click(); // → step 2, the risk card
    await expect(tooltipFor(tour, 'Risk Level')).toBeVisible({ timeout: 10_000 });

    await primaryButton(tour).click(); // → step 3, the dead target
    // The dead step is passed over and the tour is ALIVE on the next live step.
    // 'Camera Grid' never displays (it had nowhere to point) but 'Activity Feed'
    // does — that asymmetry is the fix: the tour moved ON, it did not vanish.
    await expect(tooltipFor(tour, 'Activity Feed')).toBeVisible({ timeout: 10_000 });
    await expect(tooltipFor(tour, 'Camera Grid')).toHaveCount(0);
    await expect(tourOverlay(tour)).toBeVisible();
    await tour.waitForTimeout(3_000); // FE-1's re-check: the vanish was not a frame
    await expect(tourOverlay(tour)).toBeVisible();
    await expect(joyrideRoot(tour)).toHaveCount(1);

    // And it still reaches the end and stores COMPLETION — a skipped-over step is
    // not a dismissal, so nothing was written early to fake the difference.
    // Each advance is one click on the primary button: the step above is already
    // displayed, so the next title only appears AFTER this click. (An earlier
    // draft asserted 'Event Timeline' here without clicking first and failed with
    // "element(s) not found" — the tour was healthy, sitting on step 4.)
    await primaryButton(tour).click();
    await expect(tooltipFor(tour, 'Event Timeline')).toBeVisible({ timeout: 10_000 });
    await primaryButton(tour).click();
    await expect(tooltipFor(tour, 'Settings')).toBeVisible({ timeout: 10_000 });
    await primaryButton(tour).click();
    await expect(tooltipFor(tour, 'Tour Complete')).toBeVisible({ timeout: 10_000 });
    await expect(primaryButton(tour)).toHaveAccessibleName('Finish');
    await primaryButton(tour).click();
    await expect(tourOverlay(tour)).toBeHidden({ timeout: 5_000 });
    expect(await jar(tour)).toEqual({ completed: 'true', skipped: null });

    // The loop is broken: a fresh document does NOT boot the tour again. This is
    // the half FE-1 measured as the actual user harm.
    await tour.waitForTimeout(BOOT_QUIET_MS);
    await tour.reload({ waitUntil: 'domcontentloaded' });
    await expect(tour.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(joyrideRoot(tour)).toHaveCount(0);

    // The safety net really was exercised: Joyride reported the missing target
    // (absent → 'not mounted', per modules/dom.ts:170) and our callback handled
    // it instead of stalling on it. Exactly one such step exists in this run.
    expect(noise.filter((w) => /Target not mounted/.test(w))).toHaveLength(1);

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });

  test('F-021 (skip): Skip Tour stores skipped-only and the tour never returns on reload', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const tour = await openFirstVisit(context, h);
    await expect(skipButton(tour)).toBeVisible({ timeout: 20_000 });

    await skipButton(tour).click();
    await expect(tourOverlay(tour)).toBeHidden({ timeout: 5_000 });
    // ProductTour.tsx:207-211: SKIPPED marks skipped, NOT completed.
    expect(await jar(tour)).toEqual({ completed: null, skipped: 'true' });

    // First-visit means once: a reload boots with the stored jar and the tour
    // must NOT run again (shouldShowTour false → the component renders null).
    await tour.waitForTimeout(BOOT_QUIET_MS);
    await tour.reload({ waitUntil: 'domcontentloaded' });
    await expect(tour.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(joyrideRoot(tour)).toHaveCount(0);

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });

  test('F-021 (close stores completion): Esc mid-tour writes completed immediately (NEM-3518 branch) and the tour never returns', async ({
    context,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const tour = await openFirstVisit(context, h);
    await expect(tourOverlay(tour)).toBeVisible({ timeout: 20_000 });

    await tour.keyboard.press('Escape');
    await expect(tourOverlay(tour)).toBeHidden({ timeout: 5_000 });
    // ACTIONS.CLOSE at ProductTour.tsx:193-198 marks COMPLETED, not skipped —
    // the deliberate NEM-3518 asymmetry against the Skip button.
    expect(await jar(tour)).toEqual({ completed: 'true', skipped: null });

    await tour.waitForTimeout(BOOT_QUIET_MS);
    await tour.reload({ waitUntil: 'domcontentloaded' });
    await expect(tour.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(joyrideRoot(tour)).toHaveCount(0);

    expect(() => closedByGuard(tour)).toThrow(GUARD_MESSAGE);
  });
});
