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
 *   - "clicks a result to open its detail": proven for BOTH halves. A page-1
 *     result opens the modal from the browse cache; a page-2 result the browse
 *     list has never seen now opens it too, fetched by id.
 *
 * REPAIRED — a search result is no longer a row the modal could not render.
 *   This was the second of F-048's two half-built breaks; [r211f] closes it. The
 *   defect was that `handleSearchResultClick` set only `selectedEventForModal`,
 *   and the modal's row came from a lookup in `filteredEvents` — the BROWSE list —
 *   returning null for any id that list did not hold while `isOpen` was already
 *   true, so the click opened nothing. `useEventModalRow` now completes that
 *   lookup: the browse list is tried first (so a browse-mode click still issues no
 *   new request), and a miss fetches the row from `GET /api/events/{id}`, which
 *   already served it.
 *   The subject of that click, and why it is deterministic: the naive "click a
 *   page-2 result" is FLAKY, because whether page 2's ids happen to be cached
 *   depends on whether the user scrolled while browsing (`useInfiniteScroll`, :297,
 *   disabled in search mode). The pre-`[r211b]` construction — a SOFT-DELETED
 *   victim listed by search but hidden from browse — is GONE: `[r211b]` gave search
 *   the same `deleted_at` predicate browse has (`backend/services/search.py:451`;
 *   the browse route's is `events.py:421`), so the victim is invisible to BOTH
 *   readers. The leg's live subject instead: search paginates server-side while
 *   the browse cache holds only its loaded page-1 newest 20, so every OLDER live
 *   row — search page 2 — is the one the modal had to fetch. Liveness is pinned
 *   in-leg (`GET /api/events/{id}` answers 200) because that 200 IS the request the
 *   fix makes; the old failure was the client-side lookup, not missing data.
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
 *     rows from later that day. Two probe runs failed to reach a clean read of
 *     it, so it is NOT asserted either way — and no leg of this file carries a
 *     mark for it, so the clause is simply unclaimed here.
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
  // HARD delete, victim included. Since [r211b] a soft-deleted row is invisible to
  // BOTH readers, so a lingering victim is inert — but it is still this run's row,
  // so it is hard-deleted here rather than left behind for the next run's purge.
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

    // `searchTotal` is search's own total for the token, which [r211b] now reports
    // WITHOUT the soft-deleted row, so the panel's number is the LIVE count.
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
    // version of this leg read the rows' `risk_level` field and got 0, because
    // that payload field is a `@computed_field` re-derived from risk_score
    // (schemas/search.py:44) — which is the level the filter now matches
    // (search.py:355, [r211b]). The leg that pins that agreement is
    // "the severity filter matches the level the response reports" below.
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
    // The tail is 5 rows: the 25 live hits minus the first page.
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
    // assertion — a header claiming "0 of 25" would be a different UI.
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
   * WHAT A LOADED SAVED SEARCH DOES — measured, this time.
   *
   * The clause "saves searches" has a second half the row does not mention: what a
   * saved search DOES when clicked. `handleLoadSearch` (SearchBar.tsx:189-198) calls
   * `onQueryChange(loaded.query)` and `setFilters(loaded.filters)`, closes the
   * dropdown, and — the part that matters — never submits. So loading a saved
   * search refills the form and shows nothing, and the user's next Enter is what
   * actually searches. The leg asserts exactly that: the box holds the saved text
   * and the `/api/events/search` request count does not move.
   *
   * HISTORY OF THIS MARK. The leg shipped as `test.fixme` with a docblock saying it
   * was "WRITTEN FROM THE CODE, NEVER EXECUTED": two probe runs had failed to reach
   * the read (one died on a strict-mode violation — its unanchored /name/ locator
   * resolved to the entry AND its nested delete button; the other lost its browser
   * to a full /var/lib/docker mid-run), and the parked note argued the leg could
   * not be a pass either way. Running it against a stack was the cheapest way to
   * settle that, and the measurement is unambiguous: the restore happens, zero
   * searches fire, the leg is GREEN. The parked judgement was a hypothesis about a
   * read nobody had taken; the read says the affordance is a real (if deliberately
   * non-submitting) restore, which the row's "saves searches" clause covers.
   */
  test('loading a saved search restores the form without submitting', async ({ page }) => {
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
   * THE SEVERITY FILTER NOW TESTS THE LEVEL THE RESPONSE REPORTS ([r211b]).
   *
   * `risk_level` has two live implementations and one dormant one. The stored
   * COLUMN carries whatever the create request declared
   * (`backend/models/event.py:61-63`); `computed_risk_level` is a hybrid CASE over
   * `risk_score` (`:393`: ≤29 low, ≤59 medium, ≤84 high, else critical); and the
   * response model RE-DECLARES `risk_level` as a `@computed_field`
   * (`backend/api/schemas/search.py:44`, returning `_compute_risk_level(risk_score)`
   * at `:61`), so the route's `risk_level=event.risk_level` assignment
   * (`backend/services/search.py:403`) is silently DISCARDED and the wire always
   * carries the computed value.
   *
   * Before [r211b] the predicate ran on the dormant one
   * (`Event.risk_level.in_(…)`) while the wire reported the computed one, so a
   * user filtering for the level the card displays got nothing and a level no card
   * shows is what matched — measured both directions on the probe stack (declared
   * `high` + score 91 matched `severity=high`, never `critical`). The repair (ruling
   * 211) moved the predicate onto the hybrid the payload already reports:
   * `Event.computed_risk_level.in_(filters.severity)`, `search.py:355`. That is
   * candidate (a) of the two this leg used to list; (b) — deriving the column at
   * write time — was rejected because it leaves already-stored rows mismatched.
   *
   * So this leg is now a PASSING contract for the row's "optional … severity …
   * filters" clause, and the interesting part of its shape is deliberate: the row
   * is created declaring `high` with a score of 91, i.e. a row whose stored column
   * and computed level DISAGREE. The column value is what the old predicate read,
   * so if anyone moves the filter back, the third expect reddens. The stored-column
   * disagreement is the mutation control baked into the fixture.
   */
  test('the severity filter matches the level the response reports, not the stored column', async () => {
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
      // The filter now reads the same field the payload reports: the level the
      // card displays (`critical`, from score 91) finds the row, and the stored
      // column value it used to test (`high`) finds nothing.
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
      expect(asHigh.total_count, 'the stored column value no longer matches').toBe(0);
      expect(asCritical.total_count, 'the displayed level finds its own row').toBe(1);
    } finally {
      await hardDeleteFixtureRows(harness, session, [id]);
    }
  });

  test('a page-1 result opens the modal and so does a page-2 result the browse list does not have', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const session = await bootTimeline(page, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
    const modal = page.getByTestId('event-detail-modal');

    await submit(page, SEARCH_QUERY_TOKEN);
    await expect(panelHeader(page).first()).toBeVisible();

    // POSITIVE CONTROL, and it has to be page 1: search's tie-break is
    // `started_at DESC` (search.py:465; the line moved from :432 when [r211b]
    // inserted the deleted_at predicate above it) and the browse list is ordered the same
    // way, so page 1 of search and page 1 of browse are the same 20 rows — the
    // newest (`alpha 24`) is certainly in `filteredEvents`, and its click opening
    // the modal is the shipped behaviour, not luck. It also pins that the repair
    // did not make a BROWSE-HIT click issue a request it used to skip.
    const newest = searchCard(page, 24);
    await expect(newest, 'exactly one card for this fixture row').toHaveCount(1);
    await newest.click();
    await expect(modal).toBeVisible({ timeout: 20_000 });
    await page.keyboard.press('Escape');
    await expect(modal).toHaveCount(0);

    // THE REPAIRED CLICK. This is the row that used to open nothing. Since
    // [r211b] search hides soft-deleted rows, the victim is not a subject this leg
    // can click, so the click-under-test is a search-PAGE-2 live row: the modal
    // used to resolve its row from the BROWSE page-1 cache (`filteredEvents`, the
    // infinite query's loaded pages — the newest 20, `alpha 5 … alpha 24`), while
    // the search panel paginates server-side, so every OLDER live row on search
    // page 2 (`alpha 0 … alpha 4`) was offered by search and unresolvable by the
    // modal. `alpha 0` is the oldest live row, so it is page 2's first card.
    // The modal now fetches a row the browse list does not hold by id
    // (`useEventModalRow`), so the same click opens it.
    await page.getByRole('button', { name: 'Next page' }).click();
    await expect(panelHeader(page).first()).toHaveText(new RegExp(` of ${fx.searchTotal} results`));
    const pageTwoRow = searchCard(page, 0);
    await expect(
      pageTwoRow,
      'search offers a live row the browse page-1 cache does not hold'
    ).toHaveCount(1);

    await pageTwoRow.click();
    // Identity, not mere presence: assert the modal opened ON THIS ROW. The header
    // only shows `camera_name` (identical for every fixture row), so the row's
    // unique summary — rendered in `ai-analysis-section` on the default details tab
    // (EventDetailModal.tsx:883) — is what proves the fetched row is `alpha 0` and
    // not some cached row leaking through.
    await expect(modal).toBeVisible({ timeout: 20_000 });
    await expect(
      page.getByTestId('ai-analysis-section').filter({ hasText: `${SEARCH_QUERY_TOKEN} alpha 0` })
    ).toBeVisible();
    // The search panel survives the open and the query box is untouched: the fix
    // completes the modal's lookup, it does not leave search mode.
    await expect(panelHeader(page).first()).toHaveText(new RegExp(` of ${fx.searchTotal} results`));
    await expect(queryBox(page)).toHaveValue(SEARCH_QUERY_TOKEN);

    // And the row is not merely "not in this page's cache": it is live — the
    // browse route SERVES it by id (200, not the victim's 404) — which is exactly
    // the request the modal now issues. The old failure was the client-side
    // lookup, not missing data; this line is why the fetch was the right repair.
    expect(
      await rawStatus(session, `/api/events/${fx.eventIds[0]}`),
      'the oldest live row is served by id — the route the modal now fetches'
    ).toBe(200);

    // The soft-deleted victim, the leg's OLD subject, is now correctly hidden from
    // search ([r211b]). Asserting its absence keeps this fixture honest: if search
    // ever un-hides it, this line reddens instead of the defect leg quietly
    // measuring the wrong row.
    const truth = await api<{ total_count: number; results: { id: number }[] }>(
      harness,
      session,
      `/api/events/search?q=${encodeURIComponent(SEARCH_QUERY_TOKEN)}&limit=100&camera_id=${encodeURIComponent(
        fx.cameraId
      )}`
    );
    expect(
      truth.results.some((row) => row.id === fx.victimId),
      'search no longer lists the soft-deleted row (backend/services/search.py:451)'
    ).toBe(false);
    expect(
      await rawStatus(session, `/api/events/${fx.victimId}`),
      'the browse route still refuses the soft-deleted row'
    ).toBe(404);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
