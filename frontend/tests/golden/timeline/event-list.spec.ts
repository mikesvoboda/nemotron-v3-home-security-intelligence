/**
 * FE-3 golden path (F2.3): F-043 — the timeline's event list: it opens, browses
 * as grid / list, filters, and applies its URL deep links.
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md, F-043):
 *   "opens the timeline; browses events as grid, list or mobile cards with
 *    infinite scroll; filters by camera, risk, verdict, reviewed, object type
 *    and dates; uses quick-filter chips, sort, group-by (time/camera/risk) and
 *    clustering; deep links ?camera=, ?risk_level=, ?verdict=, ?event= apply"
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - Route + root: App.tsx:259 mounts EventTimeline at /timeline; its root is
 *   `data-testid="timeline-page"` (EventTimeline.tsx:1093), present in all three
 *   view modes, so it is the boot marker in ./harness.ts.
 * - FILTERING IS SERVER-SIDE, which is what makes a DOM↔API count mirror the
 *   strongest available form of "the filter applied". The card set is
 *   `filteredEvents = pipe(getSortTransform(sortOption))(events)` (:523) — a
 *   pure client SORT of the rows the shipped infinite query returned
 *   (useEventsInfiniteQuery, limit 20, :176-186 → GET /api/events, api.ts:2270-
 *   2293). So the DOM count must equal that endpoint's `items.length` under the
 *   identical query, and a mismatch is a real defect rather than a flake.
 * - THE VIEW TOOLBAR IS NOT AVAILABLE AT ZERO EVENTS, measured, and this
 *   corrected an earlier draft of this file. `ViewToggle` (:1508) and the
 *   group-by selector sit inside `!loading && !error && filteredEvents.length >
 *   0` (:1505) — only the chips (:1204) and the filter bar (:1253) render
 *   unconditionally in browse mode. An empty stack therefore cannot exercise
 *   "browses events as grid, list", so this file gives itself rows through
 *   ./harness.ts `createTimelineFixture` (why that tool, and why it is the
 *   narrower choice than the precedent at data-ui/trash-restore.spec.ts:91-93,
 *   is recorded there).
 * - Server contract behind the filters (backend/api/routes/events.py:281-299):
 *   `camera_id` and `risk_level` are plain optional strings filtered in the
 *   WHERE (:414-415), so an empty answer is legal and the mirror — not a demand
 *   for rows — is what proves the UI sent the filter the URL carried. `verdict`
 *   is a validated enum: "Anything else is a 422, never an empty list", and
 *   `none` means "events never verified" — which is exactly what a
 *   bulk-created row is (bulk_create_events writes no verification, measured:
 *   `verification` is null), so ?verdict=none is a REAL non-empty leg rather
 *   than a 0-vs-0 mirror.
 * - Deep links: the effect at :305-334 reads `camera`, `risk_level`, `verdict`
 *   into eventFilters and sets showFilters true (reported by the toggle's
 *   aria-expanded, :1220). `?event=` opens the modal and is F-054's clause, not
 *   this spec's. Controls are read by id — `#camera-filter` (:1264),
 *   `#risk-filter` (:1287), `#sort-filter` (:1386) — so "the link applied" is
 *   asserted as "this named control holds this named value".
 * - Chips (FilterChips.tsx): real <button aria-pressed> (:70-75) inside
 *   role="group" aria-label="Filter options" (:289-290). The risk chips are
 *   labelled Critical/High/Medium (:302-316) and their pressed state is
 *   `filters.risk_level === …` (:301), so a chip click is checkable both as its
 *   own state and as sync into the select — that pairing is the real claim.
 * - Group-by: `useLocalStorage('timeline-group-by','time')` (:124) and the
 *   select is aria-label="Group events by" inside data-testid="groupby-selector"
 *   (:1514-1520). Choosing `risk` renders `data-testid={group-${level}}` per
 *   non-empty group (:1749), and the risk grouping is client-side over the
 *   loaded rows (:680-700), so with one row per level on the fixture camera all
 *   four group ids must appear.
 * - List view: rows carry `event-list-row-${id}` (EventListView.tsx:325) and
 *   sortable headers carry `aria-sort` (ascending|descending|absent, :84) plus
 *   `sort-indicator-${field}` (:105). List sorting is client-side over the same
 *   rows with `time` desc as the initial state (EventTimeline.tsx:127-128,
 *   :596-618), so row ORDER is a legitimate DOM assertion.
 * - NOT asserted here, with reasons (UR-128): (1) INFINITE SCROLL — the fixture
 *   is deliberately smaller than the page size (limit 20) so the unfiltered
 *   mirror stays exact; exercising page 2 would need ≥21 rows and would break
 *   that mirror, so the leg is left unverified rather than traded away. (2)
 *   CLUSTERING — the toggle exists (:1537-1552) but clustering needs spatially
 *   close detections; bulk-created rows carry no detections on disk. (3) the
 *   MOBILE card branch shares the grid card's testid (MobileEventCard.tsx:153 vs
 *   EventCard.tsx:388), so at <640px the DOM offers nothing that distinguishes
 *   it from the grid leg already made — a separate "mobile" test would be a
 *   duplicate dressed as coverage.
 */
/**
 * The `test`/`expect` here come from ../guard, NOT from @playwright/test, and
 * that is load-bearing rather than stylistic: guard.ts arms interception
 * blocking inside ITS OWN page-fixture override (guard.ts:97-116 → armPage), so
 * a spec that imports the base `test` gets an UNARMED page and its
 * `closedByGuard(page)` becomes a silent no-op — the unmocked contract would
 * then be unenforced while still looking asserted. (This file had that bug; the
 * first green run passed with a bare call, which is exactly how the failure
 * mode presents.) `Page` stays a type-only import from @playwright/test, which
 * is what ./harness.ts:22 does too.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  adminSession,
  api,
  closedByGuard,
  createTimelineFixture,
  FIXTURE_ROWS,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  softDeleteFixtureRows,
  waitForEventCards,
  type TimelineHarness,
  type TimelineFixture,
} from './harness';

interface EventPage {
  items: { id: number; risk_score: number; started_at: string }[];
  pagination: { total: number; has_more: boolean };
}

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

const cards = (page: Page) => page.getByTestId(/^event-card-\d+$/);
const filterToggle = (page: Page) =>
  page.getByRole('button', { name: /Hide Filters|Show Filters/ });
const chip = (page: Page, label: string) =>
  page.getByRole('group', { name: 'Filter options' }).getByRole('button', { name: label });

/** Created once for the file, tidied in afterAll; see ./harness.ts for the why. */
let fx: TimelineFixture;
let highestRiskId = 0;
let newestId = 0;

test.beforeAll(async () => {
  const session = await adminSession(harness);
  fx = await createTimelineFixture(harness, session);
  // Derived from the fixture's own row table, not from a re-read, so a typo in
  // FIXTURE_ROWS fails loudly instead of silently picking a different row.
  const top = Math.max(...FIXTURE_ROWS.map((r) => r.riskScore));
  highestRiskId = fx.eventIds[FIXTURE_ROWS.findIndex((r) => r.riskScore === top)];
  newestId = fx.eventIds[FIXTURE_ROWS.length - 1]; // latest started_at (i * 7 min)
});

test.afterAll(async () => {
  const session = await adminSession(harness);
  await softDeleteFixtureRows(harness, session, fx.eventIds);
});

/** The fixture camera's rows, read from the endpoint the UI itself queries. */
const fixtureTruth = (session: Awaited<ReturnType<typeof adminSession>>, extra = '') =>
  api<EventPage>(
    harness,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(fx.cameraId)}${extra}`
  );

test.describe('F-043 timeline event list', () => {
  test('opens the timeline: page paints, toolbar is offered, cards mirror GET /api/events', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    // Ground truth first, read from the same stack the UI reads. No interception
    // anywhere: guard.ts throws from the call itself (UR-127).
    const unfiltered = await api<EventPage>(harness, session, '/api/events?limit=20');

    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    await quietBoot(page, harness);

    await expect(page.getByTestId('timeline-page'), 'the page root paints').toBeVisible();
    await expect(
      page.getByRole('group', { name: 'View toggle' }),
      'browse mode offers the view toggle (:1505 guard needs rows — the fixture supplies them)'
    ).toBeVisible();

    await waitForEventCards(page);
    // Every fixture row must be a card: the browse claim that does not depend on
    // how many foreign rows the stack happens to hold.
    for (const id of fx.eventIds) {
      await expect(page.getByTestId(`event-card-${id}`), `fixture row ${id} renders`).toBeVisible();
    }
    // The exact DOM↔API mirror, asserted whenever the stack's first page holds
    // everything (has_more false). With more than a page present the shipped
    // query would fetch page 2 and a single limit=20 read could not be compared
    // to the DOM, so the mirror is skipped with the reason stated — the
    // per-row assertions above still ran.
    if (!unfiltered.pagination.has_more) {
      await expect(
        cards(page),
        `DOM cards mirror GET /api/events items (${unfiltered.items.length}); ` +
          `stack total=${unfiltered.pagination.total} has_more=${unfiltered.pagination.has_more}`
      ).toHaveCount(unfiltered.items.length);
    }
    // Rows exist, so the shipped empty state must NOT be on screen.
    await expect(page.getByText('No Events Found')).toHaveCount(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('deep link ?camera=<id> applies: the named select holds it, count mirrors', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    const truth = await fixtureTruth(session);

    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);

    await expect(page.getByTestId('timeline-page')).toBeVisible();
    await expect(
      page.locator('#camera-filter'),
      'the camera select holds the deep-linked id'
    ).toHaveValue(fx.cameraId);
    // The effect also opens the filters panel (:305-334 → setShowFilters(true)),
    // whose toggle reports that with aria-expanded (:1220).
    await expect(filterToggle(page), 'arriving with a URL filter opens the panel').toHaveAttribute(
      'aria-expanded',
      'true'
    );

    await waitForEventCards(page);
    await expect(
      cards(page),
      `filtered DOM mirrors GET /api/events?camera_id=… (${truth.items.length} rows)`
    ).toHaveCount(truth.items.length);
    // Nothing from another camera leaked into the filtered view.
    await expect(
      cards(page).first(),
      'the filtered set is the fixture camera only'
    ).toHaveAttribute('data-testid', new RegExp(`event-card-(${fx.eventIds.join('|')})`));
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('deep link ?risk_level=high applies, and its quick-filter chip is pressed in sync', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    const truth = await fixtureTruth(session, '&risk_level=high');

    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    await quietBoot(
      page,
      harness,
      '/timeline?risk_level=high&camera=' + encodeURIComponent(fx.cameraId)
    );

    await expect(page.locator('#risk-filter'), 'the risk select holds the level').toHaveValue(
      'high'
    );
    await waitForEventCards(page);
    await expect(
      cards(page),
      `filtered DOM mirrors GET /api/events?risk_level=high (${truth.items.length} rows)`
    ).toHaveCount(truth.items.length);

    // The chip reflects the same filter (FilterChips.tsx:301 isActive === the
    // filter value), so a deep link is visible in the chip row, not only the
    // select. Then clicking the pressed chip toggles it off (handleRiskLevelClick
    // → same-value click clears), which must empty the risk filter and widen the
    // list back to the whole camera.
    await expect(
      chip(page, 'High'),
      'the risk chip reads pressed for a deep-linked level'
    ).toHaveAttribute('aria-pressed', 'true');
    await chip(page, 'High').click();
    await expect(chip(page, 'High'), 'clicking the active chip releases it').toHaveAttribute(
      'aria-pressed',
      'false'
    );
    await expect(page.locator('#risk-filter'), 'and the select follows').toHaveValue('');
    const widened = await fixtureTruth(session);
    await waitForEventCards(page);
    await expect(
      cards(page),
      `releasing the filter mirrors the unfiltered camera read (${widened.items.length} rows)`
    ).toHaveCount(widened.items.length);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('deep link ?verdict=none applies (never-verified rows) and the chip mirrors it', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    // `none` = "events never verified" (events.py:289-291). A bulk-created row
    // has no verification (measured), so this is a REAL non-empty leg; an
    // unknown value would be a 422, never an empty list, by the same contract.
    const truth = await fixtureTruth(session, '&verdict=none');
    expect(
      truth.items.length,
      'the fixture rows must be unverified for this leg to be a real assertion'
    ).toBeGreaterThan(0);

    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    await quietBoot(
      page,
      harness,
      `/timeline?camera=${encodeURIComponent(fx.cameraId)}&verdict=none`
    );

    await expect(page.getByTestId('timeline-page')).toBeVisible();
    await expect(
      filterToggle(page),
      'the verdict deep link opens the filters panel'
    ).toHaveAttribute('aria-expanded', 'true');
    await waitForEventCards(page);
    await expect(
      cards(page),
      `filtered DOM mirrors GET /api/events?verdict=none (${truth.items.length} rows)`
    ).toHaveCount(truth.items.length);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('grid group-by risk groups every fixture row; Sort By reorders the same set', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    const truth = await fixtureTruth(session);

    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    // The camera deep link both scopes the set (so foreign rows cannot join a
    // group) and opens the filter panel, where #sort-filter lives.
    await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);

    const groupBy = page.getByLabel('Group events by');
    await expect(groupBy, 'grid view offers the group-by selector').toHaveValue('time');
    await groupBy.selectOption('risk');

    // One group per level present, keys from EventTimeline.tsx:1749.
    for (const level of ['critical', 'high', 'medium', 'low']) {
      await expect(
        page.getByTestId(`group-${level}`),
        `group-by risk renders the ${level} group`
      ).toBeVisible();
    }
    await expect(cards(page), `grouping does not lose rows (${truth.items.length})`).toHaveCount(
      truth.items.length
    );

    // Sort By is a client-side re-order of the same loaded rows (:523), so the
    // set must be unchanged while the FIRST card becomes the highest risk.
    await page.locator('#sort-filter').selectOption('risk_high');
    await expect(
      cards(page).first(),
      'Highest Risk puts the 91-point fixture row first'
    ).toHaveAttribute('data-testid', `event-card-${highestRiskId}`);
    await expect(cards(page), 'sorting kept every row').toHaveCount(truth.items.length);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('list view: rows replace cards, aria-sort reports the column, order follows it', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    const truth = await fixtureTruth(session);

    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
    await waitForEventCards(page);

    await page.getByRole('button', { name: 'Switch to list view' }).click();
    const rows = page.getByTestId(/^event-list-row-\d+$/);
    await expect(rows, 'list mode renders list rows').toHaveCount(truth.items.length);
    await expect(cards(page), 'grid cards are gone in list mode').toHaveCount(0);

    // Initial state is time/desc (EventTimeline.tsx:127-128) and the header
    // says so through aria-sort (EventListView.tsx:84).
    await expect(
      page.getByRole('columnheader', { name: /Time/ }),
      'the Time column header reports the active sort'
    ).toHaveAttribute('aria-sort', 'descending');
    await expect(rows.first(), 'newest-first puts the latest fixture row first').toHaveAttribute(
      'data-testid',
      `event-list-row-${newestId}`
    );

    // Clicking the same column toggles direction (:948-963).
    await page.getByRole('columnheader', { name: /Time/ }).click();
    await expect(
      page.getByRole('columnheader', { name: /Time/ }),
      'a second click flips to ascending'
    ).toHaveAttribute('aria-sort', 'ascending');
    await expect(rows.first(), 'oldest-first flips the row order').toHaveAttribute(
      'data-testid',
      `event-list-row-${fx.eventIds[0]}`
    );

    // Switching columns defaults to descending (:958-961) and re-sorts by risk.
    await page.getByRole('columnheader', { name: /Risk/ }).click();
    await expect(
      page.getByRole('columnheader', { name: /Risk/ }),
      'a new column starts descending'
    ).toHaveAttribute('aria-sort', 'descending');
    await expect(rows.first(), 'risk-descending leads with the 91-point row').toHaveAttribute(
      'data-testid',
      `event-list-row-${highestRiskId}`
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
