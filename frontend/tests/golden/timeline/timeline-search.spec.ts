/**
 * FE-3 golden paths (F2.3): F-048 (full-text search).
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md):
 *   F-048 "types a query with optional camera, date, severity, object and reviewed
 *          filters; saves searches; pages through results; clicks a result to open
 *          its detail"
 *
 * Four clauses, and this file drives all four — but it does NOT certify the row,
 * because the last clause has a hole in the middle of it. Read the `DEFECT` block
 * below; that is why F-048 lands `half-built` and not green.
 *
 * WHAT IS ASSERTED, and the measured number behind each claim (probe stack, UI
 * :8446 / API :18080, camera fe3-search-probe — see ./harness.ts's search block):
 *   - "types a query" … and typing is SILENT. Nine keystrokes issue zero
 *     /api/events/search requests; only Enter submits (`handleSubmit`,
 *     SearchBar.tsx:142-147, which additionally refuses while `!query.trim()`).
 *     The submit shape is `?q=<trimmed>&limit=20&offset=0`: `limit` is the
 *     component's `defaultLimit` (EventTimeline.tsx:163-170), NOT the route's own
 *     default of 50.
 *   - filters ride along and STACK. `severity=high` on the wire (api.ts:3806 —
 *     the client's param name, while the route also accepts `risk_level`),
 *     `reviewed=false` only once chosen (`if (params.reviewed !== undefined)`,
 *     :3808 — so the empty option sends NOTHING rather than `reviewed=`), and a
 *     second submit keeps the first submit's filters.
 *   - "pages through results": Next → `offset=20` + `?camera=…&search_page=2`;
 *     Previous → `offset=0`. `persistLimit:false` so `search_limit` never appears.
 *     The buttons render only while `totalPages > 1` (SearchResultsPanel.tsx:193),
 *     which is why the severity leg — 12 hits, one page — asserts their ABSENCE:
 *     that is the negative control that stops "pagination works" from meaning
 *     "pagination renders always".
 *   - "saves searches": `localStorage['hsi_saved_searches']`, and the row's own
 *     note is honest about it — saves are browser-local (useSavedSearches.ts's
 *     STORAGE_KEY, MAX_SAVED_SEARCHES=10), so this asserts storage, not a server
 *     round-trip. There IS no endpoint to assert against.
 *   - "clicks a result to open its detail": HALF TRUE, and the file says which
 *     half. A page-1 result opens the modal. A result the browse list has never
 *     seen does not.
 *
 * DEFECT — a search result can be a row the modal cannot render.
 *   `handleSearchResultClick` sets only `selectedEventForModal`; the modal's
 *   `event` prop comes from `getModalEvent()` (EventTimeline.tsx:1059-1090), which
 *   looks the id up in `filteredEvents` — the BROWSE list — and returns null when
 *   it is not there, while `isOpen` is already true. Nothing fetches the clicked
 *   row by id.
 *   The naive version of this leg ("click a page-2 result") is FLAKY, because
 *   whether page 2's ids happen to be cached depends on whether the user scrolled
 *   while browsing (`useInfiniteScroll`, :297, disabled in search mode). So the
 *   leg uses a construction instead: one fixture row is SOFT-DELETED, and the two
 *   routes disagree about it by design — search builds no `deleted_at` predicate
 *   (`search.py:281-304`) while the browse list excludes soft-deleted rows. That
 *   row is therefore a guaranteed search HIT that can NEVER be in `filteredEvents`
 *   at any page size. Measured at fixture time (see createSearchFixture): search
 *   `total_count` counts it, `GET /api/events?camera_id=…` omits it, and
 *   `GET /api/events/{id}` answers 404 — so no amount of scrolling, caching or
 *   luck can supply it, and the assertion below is a construction, not a race.
 *   The panel still advertises it: `Showing 21-26 of 26` against a browse list
 *   that says 25.
 *
 * LOCATOR TRAPS in this surface, each of which cost a probe run:
 *   - The query box has NO data-testid: `getByLabel('Search events')`
 *     (SearchBar.tsx:234).
 *   - `getByRole('button', { name })` matches by SUBSTRING against the WHOLE
 *     computed name, and a button's name includes a NESTED button's aria-label.
 *     The saved-search entry (:390) holds a delete button (:411,
 *     `Delete saved search: <name>`), so /name/ resolves to 2 and the delete's own
 *     name matches 2 as well. The entry is reached with an ANCHORED regex and the
 *     delete with `exact: true`; every card locator here is `count()`-checked
 *     before it is clicked, because `div.cursor-pointer[role=button]` also matches
 *     the sidebar's "Recent threats indicator" and `.first()` there clicks the
 *     wrong widget — a false witness, not a red test.
 *   - `getByLabel('Start Date')` is a strict-mode violation: browse's FilterChips
 *     uses the same labels. The search filters are reached by their ids.
 *   - The results header and the browse counter BOTH start with "Showing ", and
 *     JSX's `{' '}` splits the text node, so `^Showing ` with a space matches
 *     nothing. `/^Showing \d+-\d+ of/` is the search panel, unambiguously.
 *   - In the empty state TWO different buttons are named Clear Search / Clear
 *     search (different case, different code paths) — `exact: true` or nothing.
 *
 * UNCLAIMED by this file, on purpose, so the row's status stays honest:
 *   - the DATE filter clause. The search route never calls
 *     `normalize_end_date_to_end_of_day` (which IS applied at events.py:400, :607,
 *     :915, :1282 via api/validators.py:208) and builds `started_at <= end_date`
 *     raw (search.py:321-342), so `end_date=<day>` truncates to midnight and drops
 *     rows from later that day. Two probe runs failed to reach a clean read of it
 *     (see the `test.fixme` below), so it is NOT asserted either way.
 *   - `SearchResultCard`'s `aria-pressed` is DEAD: `isSelected` defaults false and
 *     SearchResultsPanel never passes it, so it always renders
 *     `aria-pressed="false"`.
 *   - the card's own keyboard activation (`role=button tabIndex=0`), the
 *     `search-results-skeleton` and error branches (a golden run cannot open an
 *     error window without mocking, and ../guard.ts:46 forbids mocking), the
 *     delete-saved-search button, and the 11th-search eviction.
 *   - search mode is not restorable from the URL (`isSearchMode` is a bare
 *     useState, :146, while `searchPagination` persists `search_page`), so
 *     `?search_page=2` reloads into browse mode with a stale param.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  SEARCH_QUERY_TOKEN,
  SEARCH_VICTIM_SUMMARY,
  adminSession,
  api,
  apiWrite,
  closedByGuard,
  createSearchFixture,
  hardDeleteFixtureRows,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  waitForEventCards,
  type SearchFixture,
  type Session,
  type TimelineHarness,
} from './harness';

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

let fx: SearchFixture;

/** The panel's page size: `searchPagination`'s defaultLimit (EventTimeline.tsx:
 *  163-170), measured on the wire as `limit=20`. */
const PAGE_SIZE = 20;

test.beforeAll(async () => {
  // The fixture waits out the camera list's 60 s cache entry on a fresh stack, so
  // the budget is generous and it is the HOOK's timeout (inside beforeAll,
  // test.setTimeout sets the hook's, not the tests').
  test.setTimeout(180_000);
  const session = await adminSession(harness);
  fx = await createSearchFixture(harness, session);
});

test.afterAll(async () => {
  const session = await adminSession(harness);
  // HARD delete, victim included: search ignores soft deletes, so a soft delete
  // here would leave the row in every later run's result count.
  await hardDeleteFixtureRows(harness, session, [...fx.eventIds, fx.victimId]);
});

/* ------------------------------- drivers ---------------------------------- */

/** Boots the timeline in BROWSE mode as the admin, tour and view-mode seeded. */
async function bootTimeline(page: Page, path = '/timeline'): Promise<Session> {
  const session = await adminSession(harness);
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  await quietBoot(page, harness, path);
  await expect(page.getByTestId('timeline-page')).toBeVisible();
  await waitForEventCards(page);
  return session;
}

/** Every /api/events/search request the page issues, captured live. The UI proxies
 *  /api on its own origin, so only `pathname` and the params are meaningful. */
function captureSearches(page: Page): URL[] {
  const seen: URL[] = [];
  page.on('request', (req) => {
    const url = new URL(req.url());
    if (url.pathname === '/api/events/search') seen.push(url);
  });
  return seen;
}

const queryBox = (page: Page) => page.getByLabel('Search events');
const panelHeader = (page: Page) => page.getByText(/^Showing \d+-\d+ of/);
const resultCards = (page: Page) => page.locator('.grid > div[role=button]');
const searchCard = (page: Page, n: number) =>
  page.getByRole('button', { name: `${SEARCH_QUERY_TOKEN} alpha ${n}`, exact: false });
const advancedToggle = (page: Page) =>
  page.getByRole('button', { name: 'Toggle advanced filters' });

/** Submits a query the way a user does — the box, then Enter. */
async function submit(page: Page, query: string): Promise<void> {
  await queryBox(page).fill(query);
  await queryBox(page).press('Enter');
  await panelHeader(page)
    .first()
    .waitFor({ timeout: 20_000 })
    .catch(() => undefined);
}

async function openAdvanced(page: Page): Promise<void> {
  if ((await advancedToggle(page).getAttribute('aria-expanded')) !== 'true') {
    await advancedToggle(page).click();
  }
}

/** A GET that EXPECTS a 404. Deliberately not `api()`: its documented contract is
 *  "a non-2xx THROWS", which is right for a spec asking the question a button asks
 *  and wrong for a leg whose assertion IS a status code. Same reason ensureCamera
 *  reads its own status instead of calling apiWrite. */
async function rawStatus(session: Session, path: string): Promise<number> {
  const res = await fetch(`${harness.api}${path}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  await res.body?.cancel().catch(() => undefined);
  return res.status;
}

/* --------------------------------- legs ----------------------------------- */

test.describe('F-048 full-text search', () => {
  test('typing is silent; Enter submits q with the page size and no camera', async ({ page }) => {
    test.setTimeout(90_000);
    // Booted WITH the camera deep link on purpose: the measured contract is that
    // the browse filter does NOT leak into the search request, i.e. `?camera=`
    // here must still produce a search with no camera_id.
    await bootTimeline(page, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
    const searches = captureSearches(page);
    const box = queryBox(page);

    // "types a query": keystrokes, not fill() — fill() sets the value in one shot
    // and would not catch a per-keystroke fetch.
    await box.pressSequentially(SEARCH_QUERY_TOKEN, { delay: 25 });
    expect(searches, 'no keystroke may fire a search request').toHaveLength(0);
    await box.press('Backspace');
    expect(searches, 'deleting a character is still typing').toHaveLength(0);

    // A BLANK query specifically: emptied, not merely shortened — the guard is
    // `if (!query.trim()) return` (SearchBar.tsx:142-147), so a one-character
    // leftover WOULD submit and would make this assertion mean nothing.
    await box.fill('');
    await box.press('Enter');
    expect(searches, 'a blank query must not submit').toHaveLength(0);

    // Surrounding whitespace on purpose: the submit is `query.trim()`
    // (SearchBar.tsx:142-147), so the wire value is the token, not the pad.
    await box.fill(`  ${SEARCH_QUERY_TOKEN}  `);
    await box.press('Enter');
    await expect(panelHeader(page).first()).toBeVisible({ timeout: 20_000 });
    expect(searches.length, 'one submit, one request').toBe(1);

    const sent = searches[0].searchParams;
    expect(sent.get('q'), 'the query travels trimmed').toBe(SEARCH_QUERY_TOKEN);
    expect(sent.get('limit'), 'the component default, not the route default of 50').toBe('20');
    expect(sent.get('offset'), 'a fresh search always starts at the first page').toBe('0');
    for (const name of ['camera_id', 'severity', 'object_type', 'reviewed']) {
      expect(sent.get(name), `an untouched filter sends no ${name}`).toBeNull();
    }

    // `searchTotal` counts the soft-deleted row, so the panel's number is the
    // SEEDED count — the first visible trace of the DEFECT leg below.
    await expect(panelHeader(page).first()).toHaveText(
      new RegExp(`^Showing 1-${Math.min(PAGE_SIZE, fx.searchTotal)} of ${fx.searchTotal} results`)
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the severity, reviewed and camera filters ride along and stack', async ({ page }) => {
    test.setTimeout(90_000);
    await bootTimeline(page);
    const searches = captureSearches(page);
    await openAdvanced(page);

    // Counted by the fixture asking the SERVER (a `severity=high` read of the same
    // route the UI calls), never derived from the fixture's own labels: the first
    // version of this leg read the rows' `risk_level` field and got 0, because the
    // payload field is a computed CASE over risk_score while the filter compares
    // the stored column. See the `test.fixme` contradiction leg for that gap.
    await page.locator('#search-severity-filter').selectOption({ value: 'high' });
    await submit(page, SEARCH_QUERY_TOKEN);
    const first = searches[searches.length - 1].searchParams;
    expect(first.get('severity'), "the client's param name is severity").toBe('high');
    await expect(panelHeader(page).first()).toHaveText(
      new RegExp(`^Showing 1-${fx.highTotal} of ${fx.highTotal} results`)
    );
    expect(await resultCards(page).count(), 'every high row, on one page').toBe(fx.highTotal);
    // Negative control for the paging clause: totalPages is 1, so the shipped
    // panel renders NEITHER button (SearchResultsPanel.tsx:193).
    await expect(page.getByRole('button', { name: 'Next page' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Previous page' })).toHaveCount(0);

    // Filters STACK: a second submit keeps severity and adds reviewed.
    await page.locator('#search-reviewed-filter').selectOption({ value: 'false' });
    await submit(page, SEARCH_QUERY_TOKEN);
    const second = searches[searches.length - 1].searchParams;
    expect(second.get('reviewed'), 'the tri-state coerces to a real boolean').toBe('false');
    expect(second.get('severity'), "a second submit keeps the first submit's filter").toBe('high');
    // Every fixture row is unreviewed (bulk create writes no review), so this is
    // the same 12 rows, not an empty answer.
    await expect(panelHeader(page).first()).toHaveText(new RegExp(` of ${fx.highTotal} results`));

    // The camera filter is the one leg that DOES put camera_id on the wire.
    await page.locator('#search-camera-filter').selectOption({ value: fx.cameraId });
    await submit(page, SEARCH_QUERY_TOKEN);
    const third = searches[searches.length - 1].searchParams;
    expect(third.get('camera_id'), 'the search camera filter is explicit').toBe(fx.cameraId);

    // And clearing one removes it from the wire: the select's '' option maps to
    // undefined, not to an empty param.
    await page.locator('#search-severity-filter').selectOption({ value: '' });
    await submit(page, SEARCH_QUERY_TOKEN);
    const fourth = searches[searches.length - 1].searchParams;
    expect(fourth.get('severity'), 'the empty option sends nothing at all').toBeNull();
    expect(fourth.get('reviewed'), 'untouched filters survive a different filter clearing').toBe(
      'false'
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('results page: Next sends the offset and the URL records the page', async ({ page }) => {
    test.setTimeout(90_000);
    await bootTimeline(page, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
    const searches = captureSearches(page);
    await submit(page, SEARCH_QUERY_TOKEN);

    await expect(panelHeader(page).first()).toHaveText(
      new RegExp(`^Showing 1-${PAGE_SIZE} of ${fx.searchTotal} results`)
    );
    expect(await resultCards(page).count(), 'one full page').toBe(PAGE_SIZE);
    const prev = page.getByRole('button', { name: 'Previous page' });
    const next = page.getByRole('button', { name: 'Next page' });
    await expect(prev).toBeDisabled(); // offset === 0 (:193)
    await expect(next).toBeEnabled();

    await next.click();
    await expect(panelHeader(page).first()).toHaveText(
      new RegExp(`^Showing ${PAGE_SIZE + 1}-${fx.searchTotal} of ${fx.searchTotal} results`)
    );
    const second = searches[searches.length - 1].searchParams;
    expect(second.get('offset'), 'the same query, one page further').toBe(String(PAGE_SIZE));
    expect(second.get('q')).toBe(SEARCH_QUERY_TOKEN);
    // The tail is 6 rows: 26 hits minus the first page.
    expect(await resultCards(page).count()).toBe(fx.searchTotal - PAGE_SIZE);
    await expect(page).toHaveURL(/search_page=2/);
    // `persistLimit:false`, so the page size never becomes a URL param.
    expect(new URL(page.url()).searchParams.get('search_limit')).toBeNull();

    await prev.click();
    await expect(panelHeader(page).first()).toHaveText(new RegExp(`^Showing 1-${PAGE_SIZE} of`));
    expect(searches[searches.length - 1].searchParams.get('offset')).toBe('0');
    await expect(prev).toBeDisabled();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('an empty answer says so, and Clear Search really leaves search', async ({ page }) => {
    test.setTimeout(90_000);
    await bootTimeline(page);
    const searches = captureSearches(page);
    await openAdvanced(page);

    // The fixture never sets object_type, so `person` cannot match: the empty
    // branch is reached without mocking anything (../guard.ts:46 forbids it).
    await page.locator('#search-object-filter').selectOption({ value: 'person' });
    await queryBox(page).fill(SEARCH_QUERY_TOKEN);
    await queryBox(page).press('Enter');
    await expect(page.getByText('No Results Found')).toBeVisible({ timeout: 20_000 });

    const sent = searches[searches.length - 1].searchParams;
    expect(sent.get('object_type')).toBe('person');
    // The empty branch swaps the panel wholesale (SearchResultsPanel.tsx:108):
    // there is no "Showing" header to read a count from, which is itself the
    // assertion — a header claiming "0 of 26" would be a different UI.
    await expect(panelHeader(page)).toHaveCount(0);
    await expect(page.getByText(/^No events match your search/)).toContainText(SEARCH_QUERY_TOKEN);
    expect(await resultCards(page).count()).toBe(0);
    // Two buttons, two casings, two code paths (:99 header / :130 empty body).
    await expect(page.getByRole('button', { name: 'Clear Search', exact: true })).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Clear search', exact: true })).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Back to browse' })).toHaveCount(1);

    await page.getByRole('button', { name: 'Clear Search', exact: true }).click();
    // Gone is the shipped escape hatch from the empty state, so assert the state
    // it promises: browse is back, the box is empty, the impossible filter cleared.
    //
    // The browse counter is the instrument, NOT `event-card-*`: this stack's saved
    // view mode renders ROWS (F-043's own test is named "list view: rows replace
    // cards"), and the card testid only exists in card mode. The counter
    // (`Showing N of M events`, EventTimeline.tsx:1459) is the shape browse takes
    // in every view mode, and its N-of-M form cannot be confused with the search
    // panel's `Showing N-M of T results` — so this also proves search mode ENDED
    // rather than merely repainting.
    await expect(page.getByText(/^Showing \d+ of \d+ events/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('button', { name: 'Back to browse' })).toHaveCount(0);
    await expect(queryBox(page)).toHaveValue('');
    await expect(page.locator('#search-object-filter')).toHaveValue('');
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('a search is saved to the browser and appears in the saved list', async ({ page }) => {
    test.setTimeout(90_000);
    await bootTimeline(page);
    const savedButton = page.getByRole('button', { name: 'Saved searches' });
    // The badge IS the count (:362). It is read as innerText because that is how
    // it was measured: `""` before any save, `"1"` after one. An absent count and
    // a zero are different renders here, and this leg says which one it expects.
    expect(
      await savedButton.innerText(),
      'a fresh browser context has no saved searches to badge'
    ).toBe('');
    await queryBox(page).fill(`${SEARCH_QUERY_TOKEN} alpha 24`);

    // `Save search` is mounted only while `query.trim()` (:302) — so an empty box
    // has nothing to save, which is the same guard the submit path uses.
    await expect(page.getByRole('button', { name: 'Save search' })).toHaveCount(1);
    await page.getByRole('button', { name: 'Save search' }).click();
    await expect(page.getByLabel('Search name')).toBeVisible();
    const save = page.getByRole('button', { name: 'Save', exact: true });
    await expect(save).toBeDisabled(); // `disabled={!searchName.trim()}` (:341)
    await page.getByLabel('Search name').fill('fe3-f048-saved');
    await expect(save).toBeEnabled();
    await save.click();

    // The claim is STORAGE, because that is what the feature is: the hook writes
    // localStorage and there is no endpoint behind it (useSavedSearches.ts).
    interface StoredSearch {
      id: string;
      name: string;
      query: string;
      filters: Record<string, string | undefined>;
      createdAt: string;
    }
    const stored = await page.evaluate(() => {
      const raw = localStorage.getItem('hsi_saved_searches');
      return raw === null ? null : (JSON.parse(raw) as StoredSearch[]);
    });
    expect(stored, "the save writes the hook's own key").not.toBeNull();
    expect(stored!.map((row) => row.name)).toContain('fe3-f048-saved');
    const entry = stored!.find((row) => row.name === 'fe3-f048-saved');
    expect(entry?.query).toBe(`${SEARCH_QUERY_TOKEN} alpha 24`);
    expect(entry?.id, 'the hook generates a per-save id').toMatch(/^search-\d+-/);
    expect(entry?.createdAt, 'a save is timestamped').toBeTruthy();
    expect(entry?.filters, 'this save carried no filters').toEqual({});

    await expect(savedButton).toContainText('1'); // the badge is the count (:362)
    await savedButton.click();
    // Anchored: the entry's name STARTS with the saved name, and its nested delete
    // button is `Delete saved search: …` (see the header's locator traps).
    const row = page.getByRole('button', { name: /^fe3-f048-saved/ });
    await expect(row).toHaveCount(1);
    await expect(
      page.getByRole('button', { name: 'Delete saved search: fe3-f048-saved', exact: true })
    ).toHaveCount(1);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /**
   * WRITTEN FROM THE CODE, NEVER EXECUTED — which is a weaker claim than the
   * other `test.fixme` in this package makes, so it is stated here in those words.
   *
   * The clause "saves searches" has a second half the row does not mention: what a
   * saved search DOES when clicked. `handleLoadSearch` (SearchBar.tsx:189-198)
   * calls `onQueryChange(loaded.query)` and `setFilters(loaded.filters)`, closes
   * the dropdown, and — the part that matters — never submits. So loading a saved
   * search refills the form and shows nothing, and the user's next Enter is what
   * actually searches.
   *
   * WHY IT IS PARKED rather than shipped as a passing leg: the request-count delta
   * was never measured. Two probe runs failed to reach the read — v5 died on a
   * strict-mode violation at this very click (its locator was an unanchored
   * /name/, which resolves to the entry AND its nested delete button), and v6's
   * browser was killed by the sandbox before the read printed (/var/lib/docker is
   * at 100 %, and Playwright's browser died 5 s into a run that had already
   * reached the dropdown). Nothing here claims to know the outcome.
   *
   * WHY IT CANNOT BE A GREEN LEG EVEN IF THE READ SUCCEEDS, on the code: the two
   * facts this file needs about loading do not coexist. If a load restores only the
   * text, the row's "saves searches" round-trips only after a manual Enter; if it
   * also restored `isSearchMode` there would be nothing to assert. Either way this
   * is a judgement about an unfinished affordance, not a pass, so the inventory row
   * must not gain a witness from it.
   *
   * To lift this: delete `.fixme`, run it, and replace the two `expect`s'
   * expectations with what the measurement actually showed.
   */
  test.fixme('loading a saved search restores the form without submitting', async ({ page }) => {
    test.setTimeout(90_000);
    await bootTimeline(page);
    const searches = captureSearches(page);
    await queryBox(page).fill(`${SEARCH_QUERY_TOKEN} alpha 24`);
    await page.getByRole('button', { name: 'Save search' }).click();
    await page.getByLabel('Search name').fill('fe3-f048-load');
    await page.getByRole('button', { name: 'Save', exact: true }).click();

    await page.getByRole('button', { name: 'Saved searches' }).click();
    const before = searches.length;
    await page.getByRole('button', { name: /^fe3-f048-load/ }).click();

    await expect(queryBox(page)).toHaveValue(`${SEARCH_QUERY_TOKEN} alpha 24`);
    expect(searches.length - before, 'loading restores, it does not search').toBe(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /**
   * THE SEVERITY FILTER FILTERS A VALUE THE ROW DOES NOT CLAIM TO HAVE.
   *
   * `risk_level` is decided at THREE sites and they do not agree. On the model
   * (`backend/models/event.py`) there is a stored column carrying whatever the
   * create request declared (`:61-63`, "the persisted risk level from LLM
   * analysis") and a `computed_risk_level` hybrid CASE over `risk_score`
   * (`:392-424`: ≤29 low, ≤59 medium, ≤84 high, else critical). The search route
   * FILTERS with the COLUMN (`Event.risk_level.in_(filters.severity)`,
   * services/search.py:331-332) but its result object assigns the column
   * (`risk_level=event.risk_level`, `:380`) into a pydantic response model that
   * RE-DECLARES `risk_level` as a `@computed_field` over `risk_score`
   * (backend/api/schemas/search.py:44, `:172-183` in schemas/events.py) — so that
   * `:380` assignment is silently discarded and the JSON the client reads is the
   * SCHEMA's computed value, a third implementation of the same thresholds.
   * The filter compares field A; the wire reports field C. (This is why a
   * reviewer must not trust the `:380` line alone — re-measure, as below.)
   *
   * Measured on the probe stack, one row at a time, all three readers
   * (single-row, browse, search) agreeing with each other and none with the
   * filter, in BOTH directions:
   *   declared `high` + score 91 → every reader says `critical`; `severity=high`
   *                              matches it (1), `severity=critical` returns 0.
   *   declared `critical` + 45   → every reader says `medium`; `severity=critical`
   *                              matches it (1), `severity=medium` returns 0.
   * So a user who filters for the level the card itself displays gets nothing,
   * and a level they never see on a card is what actually matches. The row's
   * clause is "optional … severity … filters" — the filter runs, so this is not a
   * broken control; it is a filter over a field the UI never shows. Which makes
   * it a judgement about the surface rather than a pass, i.e. `half-built`, and
   * `test.fixme` is how this repo records that (event-detail.spec.ts's read-back
   * leg is the sibling).
   *
   * TWO CANDIDATE REPAIRS, both backend, both outside this package (ruling 87):
   * (a) filter on `Event.computed_risk_level`, so the predicate and the payload
   * are the same function; or (b) make the bulk create derive the column from the
   * score so the two cannot diverge at write time. (a) is smaller and fixes rows
   * already stored; (b) leaves existing rows mismatched.
   *
   * To lift: delete `.fixme`. The expectations below are what the measurement
   * says is TRUE today, which is why they are written as the defect's evidence
   * rather than as a passing contract — a repair should FLIP the second one.
   */
  test.fixme('the severity filter matches the stored column while the UI reports a computed level', async () => {
    const session = await adminSession(harness);
    const stamp = Date.now();
    // Declared high, but a score every reader will call critical.
    const made = await apiWrite<{ results: { id: number }[] }>(
      harness,
      session,
      'POST',
      '/api/events/bulk',
      {
        events: [
          {
            batch_id: `fe3s-mismatch-${stamp}`,
            camera_id: fx.cameraId,
            started_at: new Date().toISOString(),
            risk_score: 91,
            risk_level: 'high',
            summary: `${SEARCH_QUERY_TOKEN} mismatch ${stamp}`,
          },
        ],
      }
    );
    const id = made.results[0].id;
    try {
      const row = await api<{ risk_score: number; risk_level: string }>(
        harness,
        session,
        `/api/events/${id}`
      );
      expect(row.risk_level, 'the payload reports the COMPUTED level').toBe('critical');
      // The mismatch: the row says `critical` and the only filter that finds it
      // is `high`. A repair that filters on the computed level must return 0
      // here and 1 for `critical` — i.e. this is the assertion that should flip.
      const asHigh = await api<{ total_count: number }>(
        harness,
        session,
        `/api/events/search?q=${SEARCH_QUERY_TOKEN}%20mismatch%20${stamp}&severity=high`
      );
      const asCritical = await api<{ total_count: number }>(
        harness,
        session,
        `/api/events/search?q=${SEARCH_QUERY_TOKEN}%20mismatch%20${stamp}&severity=critical`
      );
      expect(asHigh.total_count, 'the filter matched the column it was written').toBe(1);
      expect(asCritical.total_count, 'the level the UI actually displays finds nothing').toBe(0);
    } finally {
      await hardDeleteFixtureRows(harness, session, [id]);
    }
  });

  test('a page-1 result opens the modal; a row only search still has does not', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const session = await bootTimeline(page, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
    const modal = page.getByTestId('event-detail-modal');

    await submit(page, SEARCH_QUERY_TOKEN);
    await expect(panelHeader(page).first()).toBeVisible();

    // POSITIVE CONTROL, and it has to be page 1: search's tie-break is
    // `started_at DESC` (search.py:432) and the browse list is ordered the same
    // way, so page 1 of search and page 1 of browse are the same 20 rows — the
    // newest (`alpha 24`) is certainly in `filteredEvents`, and its click opening
    // the modal is the shipped behaviour, not luck.
    const newest = searchCard(page, 24);
    await expect(newest, 'exactly one card for this fixture row').toHaveCount(1);
    await newest.click();
    await expect(modal).toBeVisible({ timeout: 20_000 });
    await page.keyboard.press('Escape');
    await expect(modal).toHaveCount(0);

    // THE DEFECT. The victim is the OLDEST seeded row, so `started_at DESC` parks
    // it at the bottom of page 2 — see createSearchFixture's ordering note for why
    // oldest (a newest victim would land on page 1 and break the control above).
    await page.getByRole('button', { name: 'Next page' }).click();
    await expect(panelHeader(page).first()).toHaveText(new RegExp(` of ${fx.searchTotal} results`));
    const victim = page.getByRole('button', { name: SEARCH_VICTIM_SUMMARY, exact: false });
    await expect(victim, 'search still lists the soft-deleted row').toHaveCount(1);

    await victim.click();
    // The click does reach the handler — the panel survives and nothing else
    // changes — but the modal's lookup cannot resolve the id, so `isOpen` is true
    // over a null event and NOTHING renders (EventTimeline.tsx:1059-1090).
    await expect(modal).toHaveCount(0);
    await expect(panelHeader(page).first()).toHaveText(new RegExp(` of ${fx.searchTotal} results`));
    await expect(queryBox(page)).toHaveValue(SEARCH_QUERY_TOKEN);

    // And the row is not merely "not in this page's cache": the server itself no
    // longer serves it, so no fetch-on-open could have shown it either. Search
    // still counts it in the total the user is reading.
    expect(
      await rawStatus(session, `/api/events/${fx.victimId}`),
      'the browse route refuses the row the search panel just offered'
    ).toBe(404);
    const truth = await api<{ total_count: number; results: { id: number }[] }>(
      harness,
      session,
      `/api/events/search?q=${encodeURIComponent(SEARCH_QUERY_TOKEN)}&limit=100&camera_id=${encodeURIComponent(
        fx.cameraId
      )}`
    );
    expect(
      truth.results.some((row) => row.id === fx.victimId),
      'search is the only reader that still has it'
    ).toBe(true);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
