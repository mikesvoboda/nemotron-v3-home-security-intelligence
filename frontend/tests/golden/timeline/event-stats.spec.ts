/**
 * FE-3 golden path (F2.3): F-047 — the event statistics panel.
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md, F-047):
 *   "sees totals and a risk-level breakdown for the current camera and date
 *    filter"
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - "for the current camera and date filter" is not prose flattery of the UI:
 *   EventTimeline.tsx:198-203 mounts useEventStats with startDate/endDate/
 *   cameraId taken from `eventFilters`, and useEventStats (:93-102) turns those
 *   into GET /api/events/stats?start_date=&end_date=&camera_id= (api.ts:2314-
 *   2329). So the panel is a pure render of one endpoint under the page's
 *   filters, which makes a DOM↔API mirror the direct form of the clause.
 * - The server does the counting: total via COUNT and the breakdown via a GROUP
 *   BY, both restricted by the same three filters (events.py:609-643), and
 *   `risk_distribution` is built from the SAME counts, dropping zero levels
 *   (:668-672). Panel side, each StatCard renders `formatNumber(value)` under a
 *   label (EventStatsPanel.tsx:56-64, grid :105, cards :108-137) and
 *   RiskDistributionMini renders one bar per non-zero level with aria-label
 *   "<Level>: <n> event(s)" (RiskDistributionMini.tsx:98, bar :100-110, filter at
 *   :79) — so the SAME number is asserted twice through two independent render
 *   paths. formatNumber is `num.toLocaleString()` (:32-34), which for counts this
 *   small is the plain digit string, so the DOM side compares String(n).
 * - THE PANEL IS MOUNTED UNCONDITIONALLY in browse mode: :1154-1156 guards it
 *   with `!isSearchMode` only, and the component returns null SOLELY when the
 *   response has no `events_by_risk_level` (:94-96). Unlike ViewToggle (which
 *   sits behind a rows-exist guard and cost this batch a red run), a zero-event
 *   stack CAN assert this panel — it renders five zeros. So this file has both
 *   a zero leg and a populated one instead of trading one for the other.
 * - The date filter has TWO UI doors, and this file uses the scrubber's:
 *   TimelineScrubber's Custom Range button (`custom-range-button`,
 *   TimelineScrubber.tsx:515-527) opens DateRangePickerModal (mounted by the
 *   scrubber itself, :611-612), whose `start-date-input`/`end-date-input` are
 *   plain `type="date"` inputs (DateRangePickerModal.tsx:218, :243) and whose
 *   Apply button is `date-range-apply` (:273). Apply is disabled unless both
 *   dates are set and ordered (:117), and it calls onApply(start,end) THEN
 *   onClose() (:134-135) — so "the modal is gone" is a shipped behaviour, not an
 *   assumption. EventTimeline :1135-1140 writes the pair into
 *   eventFilters.start_date/end_date as YYYY-MM-DD, which re-keys the stats
 *   query. The end date is normalised to end-of-day server-side (events.py:607),
 *   so a one-day range covers the whole day. `timeline-reset-button` (:502-509)
 *   is the row's "resets it" half and only mounts while a custom range is active
 *   (`isCustomRangeActive={!!(start_date || end_date)}`, EventTimeline.tsx:1141).
 *   The OTHER door is the filter bar's own `#start-date-filter`/`#end-date-filter`
 *   (`:1412`, `:1432`), reachable only after "Show Filters" (:1253) — NOT
 *   exercised here, and named as an un-covered leg rather than quietly skipped.
 * - MEASURED, and it shapes the whole fixture: GET /api/events/stats counts
 *   soft-DELETED events, because :609-623 filters on dates and camera only — no
 *   deleted_at predicate — while the list route excludes them. Proof: after
 *   soft-deleting 1 of 2 rows, GET /api/events said `total: 1` while a stats
 *   read on a cache key NEVER used before the delete said `total_events: 2`.
 *   (The 60 s cache — CacheKeys.event_stats, SHORT_TTL = 60, cache_service.py:
 *   60 — makes back-to-back stats reads useless as ground truth; the first
 *   version of this probe was fooled by it and its conclusion was re-derived.)
 *   Consequence: the expected counts are DERIVED from this file's own row table,
 *   never re-read from stats, and cleanup HARD-deletes (`DELETE /api/events/
 *   bulk`, soft_delete:false, events.py:1733-1803) so no row survives to inflate
 *   a later run's totals. The frontend renders its endpoint faithfully; whether
 *   the endpoint SHOULD count trashed events is a backend question, recorded in
 *   the PR body and in the row's Notes, not something this spec hides.
 * - MEASURED so test 2's first click is not a prayer: the Custom Range button
 *   lives in the scrubber's HEADER, which the `buckets.length === 0` branch
 *   (:470-480) would replace with a "No events in selected range" box that has
 *   NO buttons. The shipped default zoom is `day` (EventTimeline.tsx:155) and the
 *   server's default window for it is 24 h with DEFAULT_RANGES.day (events.py:
 *   698-702), and buckets are created EMPTY for the whole span (:796-805) —
 *   measured 25 buckets for a camera with zero events, so the header and its
 *   button render on every stack. Probe log: /tmp/probe-stats/probe5.py.
 * - NOT asserted here, with reasons (UR-128): the scrubber's own bar/drag/zoom
 *   surface is F-046's clause; `events_by_camera` is not rendered by this panel at
 *   all; the filter bar's parallel `#start-date-filter`/`#end-date-filter` inputs
 *   (the second door above) drive the SAME eventFilters keys but are a different
 *   surface, and the preset buttons (`preset-<label>`, DateRangePickerModal.tsx:
 *   121-127) are one more way to the same state. All three stay unverified.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  adminSession,
  api,
  closedByGuard,
  createStatsFixture,
  hardDeleteFixtureRows,
  STATS_FIXTURE_ROWS,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedTourDismissed,
  type Session,
  type StatsFixture,
  type TimelineHarness,
} from './harness';

interface StatsBody {
  total_events: number;
  events_by_risk_level: Record<'critical' | 'high' | 'medium' | 'low', number>;
  risk_distribution: { risk_level: string; count: number }[];
}

/** A camera id that is FE-3's own but SEPARATE from F-043's camera: stats has no
 *  deleted-predicate, so sharing a camera would let the F-043 file's trash show
 *  up in these totals. */
const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

let fx: StatsFixture;

/** Counts this file's rows MUST produce, derived from its own row table — never
 *  re-read from the endpoint under test, or a stale answer would be its own
 *  evidence. */
const derived = () => {
  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const row of STATS_FIXTURE_ROWS) counts[row.riskLevel] += 1;
  return counts;
};

/** Server-side truth for one camera and (optionally) one date range, read from
 *  the endpoint the panel renders from. */
const statsTruth = (session: Session, range = ''): Promise<StatsBody> =>
  api<StatsBody>(
    harness,
    session,
    `/api/events/stats?camera_id=${encodeURIComponent(fx.cameraId)}${range}`
  );

/** A StatCard's value span: the card div carries the testid and the FIRST span
 *  inside it is the number (the second is the label) — EventStatsPanel.tsx:58-63. */
const stat = (page: Page, id: string) => page.getByTestId(id).locator('span').first();

test.beforeAll(async () => {
  // The fixture may wait out the camera list's 60 s cache entry on a fresh
  // stack; inside beforeAll test.setTimeout sets the HOOK's timeout, not the
  // tests'. See waitForCameraInList in ./harness.ts.
  test.setTimeout(120_000);
  const session = await adminSession(harness);
  fx = await createStatsFixture(harness, session);
});

test.afterAll(async () => {
  // HARD delete, not the soft delete F-043 uses: soft-deleted rows keep
  // counting in stats (measured), so afterAll cleanup that leaves trash would
  // make the NEXT run's totals wrong. See the header for the proof.
  const session = await adminSession(harness);
  await hardDeleteFixtureRows(harness, session, fx.eventIds);
});

test.describe('F-047 event statistics panel', () => {
  test('renders the server totals and risk breakdown for the current camera', async ({ page }) => {
    const session = await adminSession(harness);
    const truth = await statsTruth(session);
    const want = derived();

    // The fixture is the ONLY thing on this camera, so the endpoint's own
    // answer and this file's derived counts must agree before the DOM is even
    // consulted. A disagreement here is a stale-cache or counting defect, and
    // failing at this line names that instead of blaming the panel.
    expect(truth.total_events, 'fixture rows must equal the derived total').toBe(
      STATS_FIXTURE_ROWS.length
    );
    expect(
      truth.events_by_risk_level,
      'server breakdown must equal the counts this file wrote'
    ).toEqual(want);

    await seedTourDismissed(page);
    await loginAsAdmin(page, harness);
    // Arriving with ?camera= is what makes "for the current camera" a real
    // claim: the same read, unfiltered, would mix in the stack's scenario rows.
    await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);

    await expect(page.getByTestId('event-stats-panel'), 'the panel is mounted').toBeVisible();
    await expect(stat(page, 'stat-total'), 'Total Events mirrors total_events').toHaveText(
      String(truth.total_events)
    );
    for (const level of ['critical', 'high', 'medium', 'low'] as const) {
      await expect(
        stat(page, `stat-${level}`),
        `${level} card mirrors events_by_risk_level (${truth.events_by_risk_level[level]})`
      ).toHaveText(String(truth.events_by_risk_level[level]));
    }

    // The second render path: the mini chart reads risk_distribution, which the
    // server builds from the SAME counts while dropping zero levels (events.py:
    // 668-672), and the component renders a bar per level present with the count
    // in its accessible name (RiskDistributionMini.tsx:98, :105-106). So this is
    // a different code path over the same numbers, not one assertion twice.
    for (const item of truth.risk_distribution) {
      // Matched by PATTERN rather than by re-implementing the shipped
      // capitalisation and pluralisation: a cosmetic label change upstream is not
      // F-047's failure, while the level word and its count are. The \\b around
      // the count is what keeps "1 event" from matching "10 events".
      const label = new RegExp(
        `${item.risk_level}.*\\b${item.count} event${item.count === 1 ? '' : 's'}\\b`,
        'i'
      );
      await expect(
        page.getByTestId(`risk-bar-${item.risk_level}`),
        `the ${item.risk_level} bar is present and labelled with its count`
      ).toHaveAttribute('aria-label', label);
    }
    // Zero-count levels must have NO bar, which is the filter at :79 — checked
    // on the fixture's own shape (every level is non-zero here, so this asserts
    // the panel is not inventing extra bars).
    await expect(page.getByTestId(/^risk-bar-/)).toHaveCount(truth.risk_distribution.length);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the date filter re-keys the stats: a day range shows that day, Reset clears it', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    // All fixture rows are created within the last hour (createStatsFixture),
    // so "today" holds them all and a 2020 range holds none — two answers that
    // cannot both be satisfied by a panel that ignored the filter.
    const today = new Date().toISOString().split('T')[0];
    const full = await statsTruth(session, `&start_date=${today}&end_date=${today}`);
    expect(
      full.total_events,
      'a range covering today must see the whole fixture (rows anchored to now)'
    ).toBe(STATS_FIXTURE_ROWS.length);
    const empty = await statsTruth(session, '&start_date=2020-01-01&end_date=2020-01-31');
    expect(empty.total_events, 'a 2020 range must see none of them').toBe(0);

    await seedTourDismissed(page);
    await loginAsAdmin(page, harness);
    await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);

    await expect(stat(page, 'stat-total')).toHaveText(String(STATS_FIXTURE_ROWS.length));

    // Apply a range that matches NOTHING. The card must go to 0 — a panel that
    // dropped the date filter would keep showing the fixture's count.
    await page.getByTestId('custom-range-button').click();
    await expect(page.getByTestId('date-range-picker-modal')).toBeVisible();
    await page.getByTestId('start-date-input').fill('2020-01-01');
    await page.getByTestId('end-date-input').fill('2020-01-31');
    await page.getByTestId('date-range-apply').click();
    await expect(page.getByTestId('date-range-picker-modal')).toHaveCount(0);

    await expect(stat(page, 'stat-total'), 'the 2020 range reached the stats query').toHaveText(
      '0'
    );
    await expect(
      page.getByTestId('timeline-reset-button'),
      'an active custom range offers Reset'
    ).toBeVisible();

    // Reset clears start/end (EventTimeline.tsx:1141-1146), so the unfiltered
    // totals come back — the pair (filtered → 0, cleared → all) is the clause.
    await page.getByTestId('timeline-reset-button').click();
    await expect(
      page.getByTestId('timeline-reset-button'),
      'Reset removes itself once no range is active'
    ).toHaveCount(0);
    await expect(
      stat(page, 'stat-total'),
      'clearing the range restores the camera totals'
    ).toHaveText(String(STATS_FIXTURE_ROWS.length));
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('a stack with no events shows a zeroed panel, not a missing one', async ({ page }) => {
    // The panel's only null-return is a missing `events_by_risk_level`
    // (EventStatsPanel.tsx:94-96), so an empty-but-valid response renders five
    // zeros. This leg needs NO fixture: it reads a camera id that has no rows
    // and cannot exist, so the answer is 0 for every level whatever the stack
    // holds — a real judgement about the shipped empty state.
    const session = await adminSession(harness);
    const missing = await api<StatsBody>(
      harness,
      session,
      '/api/events/stats?camera_id=fe3_no_such_camera'
    );
    expect(missing.total_events).toBe(0);

    await seedTourDismissed(page);
    await loginAsAdmin(page, harness);
    await quietBoot(page, harness, '/timeline?camera=fe3_no_such_camera');

    await expect(page.getByTestId('event-stats-panel'), 'mounted even at zero rows').toBeVisible();
    await expect(stat(page, 'stat-total')).toHaveText('0');
    for (const level of ['critical', 'high', 'medium', 'low']) {
      await expect(stat(page, `stat-${level}`), `${level} renders 0`).toHaveText('0');
    }
    // The chart's own empty state, reached only when every count is zero (:113).
    await expect(page.getByTestId('risk-distribution-mini')).toBeVisible();
    await expect(page.getByTestId(/^risk-bar-/)).toHaveCount(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
