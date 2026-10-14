/**
 * FE-3 golden paths (F2.3): F-049 — the timeline's BULK mark reviewed / not
 * reviewed.
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md, F-049):
 *   "selects events (or Select All) and clicks Mark as Reviewed or Mark Not
 *    Reviewed; the list refreshes"
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - THE CLIENT LOOPS PER ID; THERE IS NO BULK ENDPOINT, which is what makes an
 *   N-request claim assertable instead of assumed. `bulkUpdateEvents`
 *   (frontend/src/services/api.ts:2461) is a `Promise.all` over `updateEvent` →
 *   `PATCH /api/events/{id}` (api.ts:2423-2428), so "bulk" is a UI word for N
 *   requests. `events.version` is SQLAlchemy's `version_id_col`
 *   (backend/models/event.py:286-298), incremented on every UPDATE the route
 *   commits (`update_event`, backend/api/routes/events.py:1939), so a row taken
 *   unreviewed→reviewed→unreviewed by the two buttons must read version ≥ 3 from
 *   its creation default of 1 — and a client that sent ONE request for a
 *   six-row selection could not produce that.
 * - THE REAL READ-BACK IS NOT "THE CARD BADGES", which is what this row's
 *   evidence cell claimed and what measuring the shipped components disproves:
 *   `grep -c reviewed` is **0** for EventCard.tsx (its badge row imports
 *   Notify/ObjectType/Risk/Snooze/Verdict badges only, :32-37) and **0** for
 *   MobileEventCard.tsx, so a GRID card carries no reviewed signal at all. What
 *   does read it back: list view's dimming (`opacity-60`,
 *   frontend/src/components/events/EventListView.tsx:323) and the per-row action
 *   guarded by `!event.reviewed` (:408 — marking reviewed REMOVES the button),
 *   and the modal's `data-testid="status-reviewed"` (EventDetailModal.tsx:1187).
 *   So "the list refreshes" is asserted as THOSE pixels plus `GET
 *   /api/events?camera=…&reviewed=` truth, whose WHERE clause is real
 *   (events.py:426-427). The row's evidence survives — through the filter, not
 *   through a badge that does not exist.
 * - SELECT ALL IS ALL-OR-NOTHING OVER THE LOADED SET (`handleToggleSelectAll`
 *   frontend/src/components/events/EventTimeline.tsx:526-540 over `filteredEvents`
 *   :523), and its button exists only in grid/grouped (:1555); list view ships its
 *   own header checkbox (EventListView.tsx:248-254). Its aria-label flips on
 *   `selectedEventIds.size === filteredEvents.length` (:1560-1562) and its TEXT
 *   becomes `${size} selected` (:1570) — two separate count claims, both asserted.
 * - SCOPING IS A SAFETY PROPERTY HERE, not tidiness: an unfiltered Select All
 *   would mark EVERY event this stack holds reviewed. Every leg therefore boots
 *   `/timeline?camera=…` (the shape ./event-detail.spec.ts:160-174 uses), so
 *   `filteredEvents` is exactly this file's rows.
 * - THE BULK BUTTONS ARE COUNT-GATED, not disabled: they render only while
 *   `selectedEventIds.size > 0` (:1580, :1602) and are disabled only in flight
 *   (:1583, :1605). "Nothing selected" is therefore observed as an ABSENCE
 *   (`toHaveCount(0)`), which is also what proves deselect-all emptied the set
 *   rather than merely renaming the button.
 * - COMPLETION IS SETTLED FROM ONE `page.evaluate` SNAPSHOT, not a chain of
 *   locator waits. `handleBulkMarkAsReviewed` fires `void refetch()` (:558) with
 *   no await, so "the bar collapsed" can be observed BEFORE the refetch lands —
 *   an expect-with-timeout would still cover it, but a locator chain that counts
 *   rows while a stale array is on screen is exactly the shape that turns a real
 *   product lag into a flake. `page.waitForFunction` reads the app's own DOM with
 *   no interception (guard.ts:46 forbids `route`/`unroute`/`routeFromHAR`/
 *   `routeWebSocket`, and that ban is why no mock is used to speed this up).
 * - A PARTIAL FAILURE CANNOT BE SUPPLIED ON THIS TIER, so its clause stays
 *   unverified and is named rather than traded for a fake. `bulkUpdateEvents`
 *   swallows each id's rejection into `results.failed` (api.ts:2461-2483) and the
 *   handler turns a non-empty `failed` into `bulkActionError` (:548-552); that
 *   string feeds `error` (:289) and `error` REPLACES the list with "Error Loading
 *   Events" (:1634-1640) — so a partial bulk failure renders as the SAME panel a
 *   shed `/api/events` wears (./harness.ts names that coat 'err429'). That is a
 *   real finding about the surface, and it is also why each leg asserts the panel
 *   is absent after its bulk: six parallel PATCHes through the stack's
 *   `zone=api rate=10r/s burst=20` limiter (frontend/nginx.conf:24) is exactly how
 *   one PATCH in a batch goes 429. A red there is honest either way — shed or
 *   genuine partial failure — and both are named; neither is papered over.
 * - THE GRID LEG RESTS ON THE FIXTURE'S 7-MINUTE SPACING, and clustering is ON by
 *   default (`useLocalStorage('timeline-clustering-enabled', true)` :117-120), so
 *   this is an instrument dependency, not a detail: `clusterEvents` joins rows from
 *   one camera whose gap is `<= 5` minutes and folds a run of ≥3 into an
 *   `event-cluster-card` (frontend/src/utils/eventClustering.ts:186, :231;
 *   EventClusterCard.tsx:194). ./harness.ts spaces FIXTURE_ROWS 7 minutes apart
 *   (:607), so every group has length 1 and the grid renders exactly
 *   `FIXTURE_ROWS.length` `event-card-<id>` nodes — which is what makes leg 1's
 *   card count an EXACT assertion (with the camera filter on, no foreign row can
 *   join it) instead of the conditional mirror ./event-list.spec.ts needs.
 * - NOT asserted here, with reasons (UR-128): (1) that PARTIAL-FAILURE branch;
 *   (2) the cluster card's own bulk action (`onBulkMarkReviewed` :1811) —
 *   clustering needs spatially close detections and bulk-created rows carry none;
 *   (3) the MOBILE swipe — MobileEventCard shares the grid card's testid
 *   (MobileEventCard.tsx:153 vs EventCard.tsx:388) and has no reviewed signal, so
 *   a "mobile bulk" test would duplicate the grid leg dressed as coverage.
 */
/**
 * `test`/`expect` come from ../guard, NOT from @playwright/test, and that is
 * load-bearing rather than stylistic: guard.ts arms interception blocking inside
 * ITS OWN page-fixture override, so a spec importing the base `test` gets an
 * UNARMED page whose `closedByGuard(page)` passes as a silent no-op. `Page` stays
 * a type-only import, as in ./harness.ts.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  adminSession,
  api,
  apiWrite,
  closedByGuard,
  createTimelineFixture,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  softDeleteFixtureRows,
  waitForEventCards,
  type Session,
  type TimelineFixture,
  type TimelineHarness,
} from './harness';

interface EventRow {
  id: number;
  reviewed: boolean;
  version: number;
}

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

/** A row no leg picks as its subject, so a bulk that "marked everything it had
 *  loaded" cannot hide behind the aggregate: this one is tracked per-row. */
const CONTROL_ROW = 5;

/** A generous expect window for the assertions that wait on `void refetch()`:
 *  the config's 3 s (playwright.config.ts:122) is for local state changes, and a
 *  post-mutation re-query behind six PATCHes is not one. */
const SETTLE = { timeout: 20_000 } as const;

const bulkReviewed = (page: Page, n: number) =>
  page.getByRole('button', { name: `Mark ${n} selected events as reviewed` });
const bulkNotReviewed = (page: Page, n: number) =>
  page.getByRole('button', { name: `Mark ${n} selected events as not reviewed` });
const allGone = (page: Page) =>
  page.getByRole('button', { name: /^Mark \d+ selected events as (not )?reviewed$/ });
/** The shipped per-row action is guarded by `!event.reviewed` (EventListView.tsx:408). */
const rowMarkButtons = (page: Page) =>
  page.getByRole('button', { name: /Mark event \d+ as reviewed$/ });
const errorPanel = (page: Page) => page.getByText('Error Loading Events');

let fx: TimelineFixture;
let session: Session;

/** The first boot of a suite pays Vite's first-compile of a NEW spec file's
 *  import graph (~11 s measured on this tier, and a single-worker golden project
 *  gives a new file no warm dep cache). The config's 15 s covers a warm boot, so
 *  the floor is raised here rather than in the shared config — an instrument
 *  floor, not a product claim. */
test.setTimeout(90_000);

test.beforeAll(async () => {
  // The fixture may wait out the camera list's 60 s cache entry on a fresh
  // stack (see waitForCameraInList in ./harness.ts); inside beforeAll
  // test.setTimeout sets the HOOK's timeout, not the tests'.
  test.setTimeout(120_000);
  session = await adminSession(harness);
  fx = await createTimelineFixture(harness, session);
});

test.afterAll(async () => {
  const s = await adminSession(harness);
  await softDeleteFixtureRows(harness, s, fx.eventIds);
});

/** How many of THIS fixture's rows the server calls reviewed, read from the
 *  endpoint the UI itself queries (events.py:426-427 applies the param). Read
 *  rather than counted from the fixture table: an earlier leg's PATCH is still on
 *  the row when a later leg starts under the golden project's ONE serial worker. */
async function serverReviewed(count: boolean): Promise<number> {
  const body = await api<{ items: { id: number }[] }>(
    harness,
    session,
    `/api/events?limit=100&reviewed=${count}&camera_id=${encodeURIComponent(fx.cameraId)}`
  );
  return body.items.length;
}

/** Single-row truth, throwing like ./event-detail.spec.ts:141 does: a harness
 *  that swallowed a 4xx into `null` would turn a missing route into a red that
 *  reads like a locator failure. */
const rowTruth = (id: number) => api<EventRow>(harness, session, `/api/events/${id}`);

/** Boot with the camera filter on — see the scoping note in the header. The
 *  shipped default view is grid (seedDefaultViewMode clears the storage key). */
async function bootTimeline(page: Page, view: 'grid' | 'list' = 'grid'): Promise<void> {
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
  await expect(page.getByTestId('timeline-page')).toBeVisible();
  await waitForEventCards(page);
  if (view === 'list') {
    await page.getByRole('button', { name: 'Switch to list view' }).click();
    // `toHaveCount`, not `toBeVisible` on a regex testid: the regex matches every
    // row and a strict-mode locator would fail on its own success (measured on
    // the probe stack — the failure printed all six rows as the violation).
    await expect(page.getByTestId(/^event-list-row-\d+$/)).toHaveCount(fx.eventIds.length);
  }
}

/** Put every fixture row back to unreviewed through the API, but ONLY for rows
 *  that need it: six blind PATCHes per reset, on top of an ~18-request boot, is
 *  how the burst limiter starts shedding this spec's own writes. Loops because
 *  apiWrite is single-resource by design. */
async function resetFixtureReviewed(): Promise<void> {
  const reviewed = await api<{ items: { id: number }[] }>(
    harness,
    session,
    `/api/events?limit=100&reviewed=true&camera_id=${encodeURIComponent(fx.cameraId)}`
  );
  for (const row of reviewed.items) {
    await apiWrite(harness, session, 'PATCH', `/api/events/${row.id}`, { reviewed: false });
  }
}

/** Wait for the bulk bar to leave, in ONE in-page read (see the header note on
 *  `void refetch()`). */
async function waitForBulkSettled(page: Page): Promise<void> {
  await page.waitForFunction(
    () =>
      !Array.from(document.querySelectorAll('button')).some((b) =>
        /^Mark \d+ selected events as (not )?reviewed$/.test(b.getAttribute('aria-label') ?? '')
      ),
    undefined,
    { timeout: 20_000 }
  );
}

test.describe('F-049 bulk mark reviewed / not reviewed', () => {
  test('Select All arms the bar over exactly the loaded rows; selecting marks nothing', async ({
    page,
  }) => {
    await bootTimeline(page);
    await resetFixtureReviewed();
    const total = fx.eventIds.length;
    // Precondition stated, not assumed: a fresh fixture is unreviewed
    // (backend/models/event.py:75), and a stale row would make every count below
    // a description of test order rather than of the product.
    expect(await serverReviewed(false), 'every fixture row starts unreviewed').toBe(total);

    // The bar only renders in grid/grouped (:1555), so assert where it lives.
    const selectAll = page.getByRole('button', { name: /Select all events|Deselect all events/ });
    await expect(selectAll, 'grid view offers the Select All control').toBeVisible();
    // Nothing selected ⇒ neither bulk action exists (the `size > 0` gate, :1580).
    await expect(allGone(page), 'no selection ⇒ no bulk actions').toHaveCount(0);

    await selectAll.click();

    // Two independent count claims on one control: the aria-label flipped
    // (:1560-1562) and its TEXT carries the number (:1570). Asserting both is what
    // distinguishes "the count is right" from "the label changed".
    await expect(
      page.getByRole('button', { name: 'Deselect all events' }),
      'the aria-label flipped at exactly the loaded count'
    ).toHaveText(`${total} selected`, SETTLE);

    await expect(
      bulkReviewed(page, total),
      `the reviewed action names the ${total} selected rows`
    ).toBeVisible();
    await expect(
      bulkNotReviewed(page, total),
      'and the not-reviewed action beside it'
    ).toBeVisible();

    // THE GRID CARRIES NO reviewed SIGNAL (EventCard.tsx has zero matches), so
    // what selection must provably NOT do is filter, dim or drop cards: the card
    // set is still the whole fixture.
    await expect(
      page.getByTestId(/^event-card-\d+$/),
      'selecting every row leaves the card set intact'
    ).toHaveCount(total);
    // And the server has seen none of it — selection is pure client state.
    expect(await serverReviewed(true), 'selection alone marks nothing').toBe(0);

    // Deselect arm, observed as the bar's DISAPPEARANCE (not just a label swap):
    // a label-only check would pass against a handler that renamed without
    // emptying the set. `exact` is load-bearing: getByRole's name is a
    // case-insensitive SUBSTRING match, so an inexact 'Select all events' would
    // also match 'Deselect all events' and this would assert the wrong state.
    await selectAll.click();
    await expect(
      page.getByRole('button', { name: 'Select all events', exact: true }),
      'the label returns'
    ).toBeVisible();
    await expect(allGone(page), 'deselect-all really emptied the selection').toHaveCount(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('bulk Mark as Reviewed marks every fixture row and the list refreshes', async ({ page }) => {
    await bootTimeline(page);
    await resetFixtureReviewed();
    const total = fx.eventIds.length;
    expect(
      await serverReviewed(false),
      'the fixture must start fully unreviewed for the delta to mean anything'
    ).toBe(total);

    // `exact` again for the same reason: this boot starts unselected, so the
    // inexact pattern would match exactly one button today but would silently
    // match BOTH labels (Select/Deselect) on any boot that inherited a
    // selection, and a strict-mode violation would read as a broken product.
    await page.getByRole('button', { name: 'Select all events', exact: true }).click();
    await bulkReviewed(page, total).click();
    await waitForBulkSettled(page);
    // The panel the harness calls 'err429' must not be up: a shed PATCH would
    // land here AND leave rows unreviewed, and the server asserts below would
    // then read as a product failure. Named so a red is diagnosable.
    await expect(errorPanel(page), 'the bulk did not degrade into the error panel').toHaveCount(0);

    // "The list refreshes": the grid has no reviewed pixel to look at, so the
    // refresh is read in list view, where reviewed has TWO shipped signals
    // (dimming EventListView.tsx:323, and the removed per-row action :408).
    await page.getByRole('button', { name: 'Switch to list view' }).click();
    await expect(page.getByTestId(/^event-list-row-\d+$/)).toHaveCount(total);
    await expect(
      rowMarkButtons(page),
      'every row is reviewed ⇒ no row still offers the mark action'
    ).toHaveCount(0, SETTLE);
    // The dimming that the same re-read produces (EventListView.tsx:323) is the
    // second, pixel-level signal that the LIST holds the new state — counted, so
    // it is a quantity and not a "something looks faded" judgement.
    await expect(
      page.locator('[data-testid^="event-list-row-"].opacity-60'),
      'the refreshed rows carry the reviewed dimming'
    ).toHaveCount(total, SETTLE);

    // Server truth, through the filter this row's evidence cell cites.
    expect(await serverReviewed(true), 'the server calls every fixture row reviewed').toBe(total);
    expect(await serverReviewed(false), 'and none unreviewed').toBe(0);

    // Per-row proof that the selection reached the server as its own write.
    const control = await rowTruth(fx.eventIds[CONTROL_ROW]);
    expect(control.reviewed, 'the tracked row was marked by this bulk').toBe(true);
    expect(control.version, 'its own PATCH advanced its version').toBeGreaterThanOrEqual(2);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('bulk Mark Not Reviewed reverses it through the list-view select-all', async ({ page }) => {
    // Deliberately runs on the state the previous leg left (one serial worker
    // over a per-file fixture): the clause "…or Mark Not Reviewed" can only be
    // asked honestly of rows that ARE reviewed, and the leg below says what it
    // needs rather than re-deriving a count from the fixture table.
    const total = fx.eventIds.length;
    // Precondition, read not assumed: the leg above left EVERY fixture row
    // reviewed. That matters beyond tidiness — the header checkbox selects all
    // LOADED rows (`handleToggleSelectAll` over `filteredEvents`), so the bulk
    // button's count is the selection size, and it equals the reviewed count only
    // because this precondition holds. Asserting it is what lets the numbers
    // below be exact instead of approximate.
    expect(await serverReviewed(true), 'this leg un-reviews the rows the leg above reviewed').toBe(
      total
    );

    await bootTimeline(page, 'list');
    await expect(
      rowMarkButtons(page),
      'a reviewed row offers no mark action (EventListView.tsx:408)'
    ).toHaveCount(0);

    // The row's "(or Select All)" clause through the OTHER door: list view ships
    // its own header checkbox (EventListView.tsx:248-254) and not the grid button.
    const header = page.getByLabel('Select all events', { exact: true });
    await expect(header, 'the list header offers its own select-all').toBeVisible();
    await header.check();

    // Named by the SELECTION size (:1607 reads `selectedEventIds.size`), which is
    // what the checkbox just produced — not by a server-side reviewed count.
    await expect(
      bulkNotReviewed(page, total),
      `the reverse action names the ${total} selected rows`
    ).toBeVisible(SETTLE);
    await bulkNotReviewed(page, total).click();
    await waitForBulkSettled(page);
    await expect(errorPanel(page), 'the bulk did not degrade into the error panel').toHaveCount(0);

    // The list refreshed: the affordance is back for every row it un-reviewed.
    await expect(
      rowMarkButtons(page),
      `the mark action returned for the ${total} un-reviewed rows`
    ).toHaveCount(total, SETTLE);
    expect(await serverReviewed(false), 'the server calls them unreviewed again').toBe(total);
    expect(await serverReviewed(true), 'and none reviewed remain').toBe(0);

    // THE LOOP-PER-ID CLAIM. `version` starts at 1 (models/event.py:67) and
    // SQLAlchemy's version_id_col increments it on every committed UPDATE
    // (models/event.py:286-298), so this row carries the whole file's history:
    // created 1 → leg 2's PATCH 2 → this leg's PATCH 3. A client that sent ONE
    // request per selection, or skipped the second transition, could not reach 3.
    const control = await rowTruth(fx.eventIds[CONTROL_ROW]);
    expect(
      control.version,
      'two UI transitions reached the server for this row'
    ).toBeGreaterThanOrEqual(3);
    expect(control.reviewed, 'and it ends unreviewed').toBe(false);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
