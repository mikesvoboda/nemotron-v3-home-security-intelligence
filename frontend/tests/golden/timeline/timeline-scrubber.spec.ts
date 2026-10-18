/**
 * FE-3 golden path (F2.3): F-046 — the timeline scrubber.
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md, F-046):
 *   "sees an event-density bar chart by hour/day/week; drags or picks a custom
 *    range to set the date filter; resets it"
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - THE CHART IS A PURE RENDER OF ONE ENDPOINT, AND THE SERVER DECIDES ITS SHAPE.
 *   `useTimelineData` issues GET
 *   /api/events/timeline-summary?bucket_size=<zoom>[&start_date][&end_date][&camera_id]
 *   (useTimelineData.ts:90-97) and maps each bucket `event_count → eventCount`,
 *   `max_risk_score → maxSeverity` via riskScoreToSeverity (:63-79).
 *   TimelineScrubber renders ONE BUTTON PER BUCKET (:555-566), height
 *   `Math.max(4, eventCount/maxCount*100)`% (:194), accessible name
 *   "<n> events at <time>, <severity> severity" (:208). So every bar is the
 *   server's own row restated, and the mirror below compares ALL of them.
 * - THE BARS ARE NOT THE EVENT COUNT. get_timeline_summary creates an EMPTY bucket
 *   for every step of the window FIRST (`while bucket_start <= end_with_tz`,
 *   events.py:800-807), then drops rows into
 *   `(started_at - window_start) // bucket` (:828-836). Window and step come from
 *   the zoom alone while no dates are set: DEFAULT_RANGES/BUCKET_SIZES
 *   (events.py:690-702) give day → 24 h at 1 h = **25 bars**, week → 7 d at
 *   1 d = **8 bars**. Six fixture rows are therefore NOT six bars; a spec written
 *   off the row table would be a false red. The honest shape — one bucket at
 *   100 %, the rest at the 4 % floor — is what leg 1 asserts.
 * - WHICH RESPONSE THE DOM IS COMPARED TO, and why the fixture is seeded at ONE
 *   instant. With no dates the window is `now - 24 h → now` (events.py:744-747),
 *   so every bucket EDGE slides with the wall clock. Two consequences, both
 *   designed out: (1) the mirror compares the DOM to the body of THE PAGE'S OWN
 *   RESPONSE (captured around one explicit reload — the idiom this suite already
 *   uses, analytics.spec.ts:236, performance-history.spec.ts:54-61) rather than to
 *   a Node read taken seconds later, so the two sides cannot be describing
 *   different windows; (2) all six rows share ONE `started_at`, because a single
 *   instant can never be split by a bucket edge — a spread fixture (7 min apart,
 *   say) could be divided by an edge that moves between two reads, which is a
 *   flake with no bug behind it. Node reads are used only where the window is
 *   DATE-BOUND, where drift is impossible.
 * - THE TIMESTAMP INSIDE THE BAR NAME IS NOT COMPARED TEXTUALLY. It is
 *   `new Date(ts).toLocaleString()` rendered by the BROWSER (:208) and this suite
 *   runs three engines with no pinned locale; reproducing it in Node would be a
 *   locale flake dressed up as a feature assertion. The count and the severity
 *   word — the parts that carry the clause — are compared exactly, and the
 *   bucket's identity is pinned by `data-bucket-index` (:200), which is DOM-side
 *   and engine-independent. A name that does not parse at all fails loudly.
 * - THE DATE FILTER REALLY LEAVES THE BROWSER AND ARRIVES DAY-TRUNCATED. A bar
 *   click emits a FINE range ({startDate: bucket.timestamp, endDate: +1 h at day
 *   zoom}, :326-341) but EventTimeline truncates BOTH ends with `.split('T')[0]`
 *   before storing them (:1122-1127), and useTimelineData/fetchEvents send
 *   whatever they are given (useTimelineData.ts:93-94, api.ts:2279-2280). So any
 *   day bar writes start == end == one calendar day — NOT the clicked bucket.
 *   MEASURED consequence, asserted rather than wished away: this route applies no
 *   end-of-day normalisation (the LIST route does, via
 *   normalize_end_date_to_end_of_day at :398-400; get_timeline_summary never calls
 *   it), so `start == end` collapses the scrubber's own window to ONE bucket and
 *   the strip visibly redraws as a single bar. Deliberately NOT claimed for the
 *   two-end drag: when the 24 h window straddles UTC midnight its first and last
 *   buckets are different calendar days, so a drag can legitimately produce a
 *   one-day window instead. That leg asserts the DOM against a Node read of the
 *   params the page actually sent, which is true on any clock.
 * - THE PICKER IS AN INDEPENDENT CONTROL (NEM-3585) and does NOT share that
 *   truncation: `onCustomRangeSelect` writes the pair verbatim
 *   (EventTimeline.tsx:1134-1140); its inputs are plain `type="date"`
 *   (`start-date-input`/`end-date-input`, DateRangePickerModal.tsx:209-256); Apply
 *   is `disabled={!isValid}` and calls onApply(start,end) THEN onClose()
 *   (:116-136, :266-276). Its ordering guard is LIVE, not submit-time:
 *   validationError is a memo (:108-114) feeding the red `date-range-error` alert
 *   directly (:261-270), so a reversed pair shows the message while the modal is
 *   still open — leg 2 asserts that BEFORE committing anything.
 * - "resets it" is `timeline-reset-button`, mounted ONLY while
 *   `isCustomRangeActive && onReset` (:501-510) where
 *   `isCustomRangeActive={!!(start_date || end_date)}` (EventTimeline.tsx:1141),
 *   and its handler clears both dates (:1142-1147). Its appearance after a pick
 *   and its disappearance after the click are both shipped semantics, asserted in
 *   all three legs. Note the asymmetry worth keeping: a BAR CLICK writes the same
 *   two keys, so it activates the custom range too — leg 1 round-trips through
 *   that door, leg 3 through the drag, leg 2 through the picker.
 * - ZOOM IS A REQUEST PARAMETER, not a re-shape of cached data: ZoomControls
 *   renders three buttons in `role=group aria-label="Zoom controls"` with
 *   `aria-pressed={zoomLevel === level}` (:111-130), the shipped default is 'day'
 *   (EventTimeline.tsx:155), and the level goes into both the query key and the
 *   URL (useTimelineData.ts:107, :91). Leg 2 asserts the pressed state, the bar
 *   count the server's constants imply (week = 8), and that week zoom's coarser
 *   1-day bucket holds the whole fixture — same rows, different aggregation, which
 *   only real server-side bucketing produces.
 * - CLICK vs DRAG ARE DIFFERENT PATHS and the drag has a real guard:
 *   `handleMouseUp` fires `onTimeRangeChange` ONLY when the two computed indices
 *   differ (:422-439); `handleMouseMove` computes an index and DISCARDS IT
 *   (`// Visual feedback could be added here` / `void currentIndex`, :381-393), so
 *   there is nothing visual to assert mid-drag; and neither mouse handler calls
 *   setSelectedIndex, while the container is `role=slider` with
 *   `aria-valuenow={selectedIndex}` which starts at 0 (:253, :531-539). So leg 3
 *   asserts three shipped truths at once: a same-bucket drag dispatches nothing
 *   (Reset never appears — the negative control that a build firing on every
 *   mouseup would fail), a two-bucket drag does set the filter, and neither drag
 *   moves the selection indicator.
 * - NOT asserted here, with reasons (UR-128), so the row is not over-credited:
 *   (a) `viewport-indicator` (:570-578) is UNREACHABLE IN THIS APP — it renders
 *   only when the `currentRange` prop is set (:307-322) and the page's mount
 *   (EventTimeline.tsx:1119-1137) never passes it. A golden run cannot reach it;
 *   naming that is more honest than a component test that invents the prop.
 *   (b) hour zoom (1 h at 5-min steps = 13 bars) is not clicked. The same two
 *   constants are exercised by day and week, and 5-minute buckets are the shape
 *   most exposed to this route's 60 s Redis cache (:756-764). Named, not skipped
 *   silently.
 *   (c) The keyboard path (`handleKeyDown` :430-465 — arrows/Home/End/Enter, which
 *   re-uses handleBarClick) is NOT exercised.
 *   (d) `timeline-scrubber-skeleton` (:78-84) needs an in-flight window. Unclaimed.
 *   (e) The `hover` tooltip (:155-172, role=tooltip) is not asserted: hover state
 *   is client-local and the count it shows is the same number leg 1 already mirrors.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  FIXTURE_ROWS,
  adminSession,
  apiShell as api,
  apiWrite,
  closedByGuard,
  loginAsAdminShell as loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  settledReload,
  waitForCameraInList,
  type Session,
  type TimelineHarness,
} from '../harness';

/* A FOURTH camera, for a reason specific to this row. FE-3's other cameras exist
 * because its endpoints disagree about soft-deleted rows (stats counts them, the
 * list does not). The scrubber's endpoint EXCLUDES them —
 * `Event.deleted_at.is_(None)`, events.py:773 — so sharing FIXTURE_CAMERA_NAME
 * would leave leg 1's bar counts a function of what the F-043 file happened to
 * leave in the trash. A private camera makes "this camera holds exactly these six
 * rows" true by construction, which is what every number below rests on. */
const SCRUB_CAMERA_NAME = 'fe3-scrub-probe';

/** Day zoom: a 24 h window at 1 h steps, inclusive at both ends (the constants at
 *  events.py:690-702 plus the `<=` loop at :800) → 25 bars. */
const DAY_BARS = 25;
/** Week zoom: 7 days at 1 day, same inclusive loop → 8 bars. */
const WEEK_BARS = 8;
/** How far back the fixture sits. The scrubber's unfiltered window is the last
 *  24 h, so the rows are ~22 h inside its trailing edge and ~1.7 h from `now`:
 *  no bucket edge that drifts by seconds can move them in or out. */
const ROWS_AGO_MIN = 100;

interface TimelineBucketBody {
  timestamp: string;
  event_count: number;
  max_risk_score: number;
}
interface TimelineSummaryBody {
  buckets: TimelineBucketBody[];
  total_events: number;
  start_date: string;
  end_date: string;
}

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

let cameraId = '';
let eventIds: number[] = [];

const summaryPath = (zoom: string, range: string): string =>
  `/api/events/timeline-summary?bucket_size=${zoom}&camera_id=${encodeURIComponent(cameraId)}${range}`;

/** Server answer read the way the page reads it. Only for PRE-FLIGHT claims and
 *  for windows named by a DATE (drift-free); the unfiltered mirror in leg 1 uses
 *  the page's own response body instead — see the header. */
const summary = (session: Session, zoom: string, range = ''): Promise<TimelineSummaryBody> =>
  api<TimelineSummaryBody>(harness, session, summaryPath(zoom, range));

/** The scrubber's header: "<total> event[s] in <N> hour[s]|day[s]"
 *  (TimelineScrubber.tsx:496) over `buckets.reduce(...)` (:271-278).
 *  MEASURED, two things this locator has to dodge. (1) The `^` anchor: the
 *  enclosing div's text also contains the zoom buttons' labels, so an unanchored
 *  pattern matches more than the span. (2) The ` in ` suffix: clicking a bar
 *  MOVES THE POINTER OVER IT, which mounts the hover tooltip whose own text is
 *  exactly "<count> events" (:169-171) — so `/^0 events/` resolves to BOTH the
 *  header and that tooltip and fails strict mode. Every header render ends with
 *  " in " (the range text, empty for a one-bucket window but still preceded by
 *  the literal " in "), and the tooltip's never does, so this is disambiguated by
 *  the shipped template rather than by a class name. */
const headerLine = (page: Page, total: number) =>
  page.getByTestId('timeline-scrubber').getByText(new RegExp(`^${total} events? in`));

/** Bar geometry, read once per leg. `data-bucket-index` is the map index the
 *  component assigned (:199), so a row here is tied to a bucket by DOM-side
 *  evidence rather than by assuming the render order. */
interface RenderedBar {
  index: number;
  height: number;
  count: number;
  severity: string;
}
const readBars = (page: Page): Promise<RenderedBar[]> =>
  page.getByTestId('timeline-bar').evaluateAll((els) =>
    els.map((el) => {
      const label = el.getAttribute('aria-label') ?? '';
      // The shape from TimelineScrubber.tsx:208. Anything that fails to parse is
      // a renamed/reshaped bar and must fail loudly, not silently sample fewer.
      const m = /^(\d+) event[s]? at (.+), (low|medium|high|critical) severity$/.exec(label);
      return {
        index: Number(el.getAttribute('data-bucket-index')),
        height: parseFloat((el as HTMLElement).style.height),
        count: m ? Number(m[1]) : NaN,
        severity: m ? m[3] : `<unparsed:${label}>`,
      };
    })
  );

/** riskScoreToSeverity restated from useTimelineData.ts:63-68 ON PURPOSE: the
 *  mirror has to say what the bar SHOULD claim from the server's raw
 *  `max_risk_score`, not echo what the client computed. Change the shipped bands
 *  and this fails — that is the point. */
function expectedSeverity(riskScore: number): string {
  if (riskScore >= 85) return 'critical';
  if (riskScore >= 60) return 'high';
  if (riskScore >= 30) return 'medium';
  return 'low';
}

test.describe('F-046 timeline scrubber', () => {
  // Six boots of a 25-bar chart, each behind BOOT_QUIET_MS. The config's 15 s is
  // a per-TEST timeout (playwright.config.ts:112) and a quiet boot eats most of
  // it; 90 s is this suite's own precedent (analytics.spec.ts:89).
  test.setTimeout(90_000);

  test.beforeAll(async () => {
    test.setTimeout(180_000); // this HOOK may wait out the camera list's 60 s cache
    const session = await adminSession(harness);

    // The harness keeps ensureCamera private, and its documented reason is right:
    // a 409 here is an EXPECTED answer, so this one call reads its own status
    // rather than borrowing apiWrite's "non-2xx throws" contract. The id is READ,
    // never derived — the backend folds dashes to underscores and an assumed id
    // breaks the day that changes.
    const res = await fetch(`${harness.api}/api/cameras`, {
      method: 'POST',
      headers: {
        Cookie: `${session.name}=${session.value}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name: SCRUB_CAMERA_NAME, folder_path: '/cameras/fe3_scrub_probe' }),
    });
    if (res.status >= 200 && res.status < 300) {
      const created = (await res.json()) as { id?: string };
      if (!created.id) throw new Error(`fixture: POST /api/cameras 2xx had no id`);
      cameraId = created.id;
    } else if (res.status === 409) {
      await waitForCameraInList(harness, session, SCRUB_CAMERA_NAME);
      const list = await api<{ items: { id: string; name: string }[] }>(
        harness,
        session,
        '/api/cameras'
      );
      cameraId = list.items.find((c) => c.name === SCRUB_CAMERA_NAME)?.id ?? '';
      if (!cameraId)
        throw new Error(`fixture: '${SCRUB_CAMERA_NAME}' 409d but absent from the list`);
    } else {
      throw new Error(`fixture: POST /api/cameras answered ${res.status}: ${await res.text()}`);
    }

    // A previous run's residue would sit in a DIFFERENT bucket and move leg 1's
    // shape, so clear this camera first (hard: the summary route excludes soft-
    // deleted rows anyway, but leaving them would make "exactly six rows" false
    // for the list route leg 2's picker reads through).
    const stale = await api<{ items: { id: number }[] }>(
      harness,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
    );
    if (stale.items.length) {
      await apiWrite<unknown>(harness, session, 'DELETE', '/api/events/bulk', {
        event_ids: stale.items.map((r) => r.id),
        soft_delete: false,
      });
    }

    // Rows anchored to NOW (same shared-instant reasoning as createStatsFixture
    // in ./harness.ts — cited by function, not by line, because line cites there
    // went stale the moment the midnight-window fix landed): the scrubber's
    // default window is `now - 24 h → now`, so a fixture pinned to a calendar
    // date walks out of it and the bars go flat. ONE shared instant, so no
    // drifting bucket edge can ever split the fixture — see the header.
    const salt = Date.now();
    const instant = new Date(Date.now() - ROWS_AGO_MIN * 60_000).toISOString();
    const events = FIXTURE_ROWS.map((row, i) => ({
      batch_id: `fe3sc-${salt}-${i}`, // UNIQUE per row (measured UniqueViolationError)
      camera_id: cameraId,
      started_at: instant,
      risk_score: row.riskScore,
      risk_level: row.riskLevel,
      summary: `FE-3 scrubber fixture row ${i} (${row.riskLevel})`,
    }));
    const bulk = await apiWrite<{ succeeded: number; results: { id: number | null }[] }>(
      harness,
      session,
      'POST',
      '/api/events/bulk',
      { events }
    );
    if (bulk.succeeded !== events.length) {
      throw new Error(`scrubber fixture: bulk create succeeded ${bulk.succeeded}/${events.length}`);
    }
    eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  });

  test.afterAll(async () => {
    const session = await adminSession(harness);
    await apiWrite<unknown>(harness, session, 'DELETE', '/api/events/bulk', {
      event_ids: eventIds,
      soft_delete: false,
    });
  });

  /** A boot that lands ON this camera. `?camera=` is what makes the bars this
   *  camera's (EventTimeline.tsx:305-328 writes the param into the filters), and
   *  the two seeds are the ones the sibling files need: a fresh context boots the
   *  product tour whose overlay eats pointer events, and the stored view mode
   *  would otherwise decide which list body renders. */
  async function boot(page: Page): Promise<void> {
    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(cameraId)}`);
  }

  /** Boot, then re-drive ONE settled reload behind a listener, so the body
   *  returned is the body the page rendered FROM — not a second read of a window
   *  that has since slid. `settledReload` (harness.ts:323) is used rather than a
   *  bare page.reload because the shared nginx bucket (rate=10r/s burst=20) can
   *  shed a boot, and a shed boot fail-closes at /setup — which would surface as
   *  a locator error that reads like a FEATURE failure.
   *
   *  MEASURED, and it is the reason the predicate names the camera: the boot
   *  issues TWO summary requests, because `?camera=` reaches `eventFilters`
   *  through an effect (EventTimeline.tsx:305-328) and the first render has no
   *  camera yet. A path-only predicate caught the UNFILTERED one — 9 events
   *  stack-wide instead of this camera's 6 — which is the same trap as mirroring
   *  against a second read, wearing a different hat.
   *
   *  The body is read AT RESOLUTION (`.then(r => r.json())`), not after the
   *  reload loop returns. It used to `await settledReload()` and THEN
   *  `res.json()`, and that is the 3/3 `Network.getResponseBody: No resource with
   *  given identifier found` run 38488280792 hit on all three attempts: `res`
   *  resolves at the response EVENT during the first drive, but
   *  `settledReload`→`driveUntilBooted` reloads up to 4 times when the shared
   *  nginx bucket sheds a boot, and each navigation tears down the document that
   *  owned the matched request, so CDP has evicted its body by the time a
   *  deferred `.json()` asks for it. The fetch SUCCEEDED (the panel rendered from
   *  it) — only the read handle was dead, so this was transport, not a dropped
   *  summary body. In isolation the boot lands on drive 1 and never re-navigates,
   *  which is why no local single-file run reproduced it: it needs the full-suite
   *  bucket pressure to force a second drive. Reading at resolution issues the
   *  CDP `getResponseBody` while the owning document is still current. */
  async function bootAndCapture(page: Page): Promise<TimelineSummaryBody> {
    await boot(page);
    const captured = page
      .waitForResponse(
        (r) =>
          r.request().method() === 'GET' &&
          new URL(r.url()).pathname === '/api/events/timeline-summary' &&
          new URL(r.url()).searchParams.get('camera_id') === cameraId &&
          // Only a SUCCESS is "the body the page rendered from": the predicate
          // used to ignore status, so a boot the nginx bucket shed (429 whose
          // body is nginx HTML, not the summary) could satisfy it, and the
          // deferred read then failed as an eviction instead of as what it was.
          r.status() === 200,
        { timeout: 30_000 }
      )
      .then((r) => r.json());
    await settledReload(page);
    return (await captured) as TimelineSummaryBody;
  }

  test('sees a 24-hour event-density chart whose every bar mirrors the server, and a bar click sets and resets the filter', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    const truth = await bootAndCapture(page);
    const bars = page.getByTestId('timeline-bar');

    // The instrument's own shape first: if the window/step constants moved, every
    // count below would be meaningless, so name that here.
    expect(truth.buckets.length, 'day zoom = a 24 h window at 1 h steps, inclusive').toBe(DAY_BARS);
    expect(truth.total_events, "this camera holds exactly this file's rows").toBe(
      FIXTURE_ROWS.length
    );
    await expect(bars, 'one button per bucket').toHaveCount(DAY_BARS);

    /* THE CLAUSE'S "event-density": all 25 bars, not a sample. Count and severity
     * come from the same response the page rendered from; the timestamp inside the
     * accessible name is Chromium's toLocaleString and is therefore parsed out of
     * the shape rather than reproduced in Node (header: locale). */
    const rendered = await readBars(page);
    expect(
      rendered.map((b) => b.index),
      'bucket indices are 0..24 in order'
    ).toEqual(truth.buckets.map((_, i) => i));
    expect(
      rendered.map((b) => b.count),
      "every bar states its own bucket's count"
    ).toEqual(truth.buckets.map((b) => b.event_count));
    expect(
      rendered.map((b) => b.severity),
      'every bar states the severity its max risk score maps to'
    ).toEqual(truth.buckets.map((b) => expectedSeverity(b.max_risk_score)));

    /* Heights are the DENSITY: the bucket holding the fixture is full and every
     * empty bucket sits at the 4 % floor (TimelineScrubber.tsx:194), which a chart
     * that ignored its data could not produce. */
    const counts = truth.buckets.map((b) => b.event_count);
    const max = Math.max(...counts);
    expect(counts, 'all six rows are in one 1-hour bucket (shared instant)').toContain(
      FIXTURE_ROWS.length
    );
    expect(
      rendered.filter((b) => b.height === 100).length,
      'every bucket with the maximum count is drawn at full height'
    ).toBe(counts.filter((c) => c === max).length);
    expect(
      rendered.filter((b) => b.height <= 4.001).length,
      'every zero bucket is drawn at the 4 % floor, not at zero height'
    ).toBe(counts.filter((c) => c === 0).length);

    await expect(
      headerLine(page, truth.total_events),
      "the header total is the buckets' own sum"
    ).toBeVisible();

    // The shipped default, and the group's accessible shape.
    const zoom = page.getByRole('group', { name: 'Zoom controls' });
    await expect(zoom.getByRole('button', { name: 'day', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    await expect(zoom.getByRole('button', { name: 'week', exact: true })).toHaveAttribute(
      'aria-pressed',
      'false'
    );

    /* ── "drags or picks a custom range to set the date filter", over a BAR
         CLICK, then "resets it". The clicked bar is CHOSEN, not assumed. It must
         hold no fixture row, AND its bucket must fit inside ONE calendar day,
         which is what the end_date claim below needs. A hard-coded index cannot
         say that: with no dates the window is [now − 24 h, now] at 1 h steps
         (events.py:793-794, loop at :848), so bucket k spans midnight exactly
         when (hour(now) + k) % 24 == 23 — index 1 fails at UTC hour 22, indices
         0 and 24 at hour 23. That is what reddened this leg on main at d3e19d007
         (CI run 38967875214, ended 22:07:54Z) and on #7225 (run 38973909316,
         ended 22:56:53Z): three identical failed attempts each — Expected
         "2026-10-15" / Received "2026-10-16" — so reproduced, not flaked. ── */
    const dayOf = (iso: string): string => iso.split('T')[0];
    const plusOneHour = (iso: string): string =>
      new Date(new Date(iso).getTime() + 60 * 60 * 1000).toISOString();
    const clickedIdx = truth.buckets.findIndex(
      (b) => b.event_count === 0 && dayOf(plusOneHour(b.timestamp)) === dayOf(b.timestamp)
    );
    expect(
      clickedIdx,
      'the 24 h window holds a bar that is both empty and inside one calendar day'
    ).toBeGreaterThan(-1);
    expect(
      truth.buckets[clickedIdx].event_count,
      'the bar clicked for the filter leg holds no fixture row'
    ).toBe(0);
    const filtered = page.waitForRequest(
      (r) =>
        r.method() === 'GET' &&
        new URL(r.url()).pathname === '/api/events/timeline-summary' &&
        new URL(r.url()).searchParams.has('start_date'),
      { timeout: 20_000 }
    );
    await bars.nth(clickedIdx).click();
    const req = await filtered;
    const params = new URL(req.url()).searchParams;
    expect(params.get('bucket_size'), 'the zoom level rides along').toBe('day');

    /* MEASURED DAY-TRUNCATION, asserted as shipped. The scrubber emitted
     * {start: the clicked bucket's ISO instant, end: +1 h} (TimelineScrubber.tsx:
     * :326-345, duration + toISOString at :333-339); the page kept only the
     * calendar day of each (EventTimeline.tsx:1158-1159). The expected value is
     * built with the SHIPPED transform (slice at 'T') on the same string the
     * client had, so this compares the page to the contract rather than to my
     * reading of it — and the bar was picked precisely because its +1 h shares
     * its day, so the claim is about the truncation, not about the clock. */
    const clickedDate = dayOf(truth.buckets[clickedIdx].timestamp);
    expect(params.get('start_date'), "the click reached the scrubber's own endpoint").toBe(
      clickedDate
    );
    expect(
      params.get('end_date'),
      'the fine end was truncated to the SAME day — a day bar selects a calendar day, not a bucket'
    ).toBe(clickedDate);

    // And what that does to the chart: no end-of-day normalisation on this route
    // (contrast :398-400), so start == end is a one-bucket window.
    const collapsed = await summary(
      session,
      'day',
      `&start_date=${clickedDate}&end_date=${clickedDate}`
    );
    expect(collapsed.buckets.length, 'a same-day window collapses to one bucket').toBe(1);
    await expect(bars, 'the strip redraws as that single bucket').toHaveCount(1);
    await expect(
      headerLine(page, collapsed.total_events),
      'the header follows the filtered buckets'
    ).toBeVisible();

    /* "resets it": the button is there because the click set the very filters
     * isCustomRangeActive reads, and clicking it clears them (EventTimeline.tsx:
     * 1142-1147), so it then removes itself. */
    const reset = page.getByTestId('timeline-reset-button');
    await expect(reset, 'an active range mounts Reset').toBeVisible();
    await reset.click();
    await expect(reset, 'Reset clears the filters and so removes itself').toHaveCount(0);
    await expect(bars, 'the unfiltered 25-bucket strip comes back').toHaveCount(DAY_BARS);
    await expect(
      headerLine(page, FIXTURE_ROWS.length),
      'the fixture is visible again'
    ).toBeVisible();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('zooms to week, and the custom picker guards, filters and resets', async ({ page }) => {
    const session = await adminSession(harness);

    // Pre-flight on the window the week leg is about to ask for. A 7-day span at
    // 1-day steps → 8 buckets; the fixture is ~100 min old, so it is ~6.7 days
    // inside the trailing edge — drift of seconds cannot move it, and one shared
    // instant means no edge can split it.
    const week = await summary(session, 'week');
    expect(week.buckets.length, 'week zoom = 7 d at 1 d steps, inclusive').toBe(WEEK_BARS);
    expect(week.total_events, 'week zoom sees the whole fixture').toBe(FIXTURE_ROWS.length);

    await boot(page);
    const bars = page.getByTestId('timeline-bar');
    await expect(bars, 'the page boots at day zoom').toHaveCount(DAY_BARS);

    await page
      .getByRole('group', { name: 'Zoom controls' })
      .getByRole('button', { name: 'week', exact: true })
      .click();
    await expect(
      page.getByRole('button', { name: 'week', exact: true }),
      'the pressed state follows the zoom'
    ).toHaveAttribute('aria-pressed', 'true');
    await expect(bars, 'week zoom asks the server for 1-day buckets and gets 8 bars').toHaveCount(
      WEEK_BARS
    );
    const weekRendered = await readBars(page);
    expect(
      weekRendered.filter((b) => b.count === FIXTURE_ROWS.length).length,
      'one 1-day bucket holds all six rows'
    ).toBe(1);
    expect(
      weekRendered.reduce((s, b) => s + b.count, 0),
      'the 8 bars together account for the whole fixture, no invented events'
    ).toBe(FIXTURE_ROWS.length);
    await expect(headerLine(page, FIXTURE_ROWS.length), 'header total at week zoom').toBeVisible();

    /* ── the picker's live ordering guard, asserted BEFORE anything commits ── */
    await page.getByTestId('custom-range-button').click();
    await expect(page.getByTestId('date-range-picker-modal'), 'the modal opens').toBeVisible();
    const today = new Date().toISOString().slice(0, 10);
    await page.getByTestId('start-date-input').fill(today);
    await page.getByTestId('end-date-input').fill('2020-06-01');
    await expect(
      page.getByTestId('date-range-error'),
      'the guard fires on input, not on submit (validationError is a memo)'
    ).toContainText('End date cannot be before start date');
    await expect(
      page.getByTestId('date-range-apply'),
      'a reversed pair cannot be applied'
    ).toBeDisabled();
    await page.getByTestId('date-range-cancel').click();
    await expect(page.getByTestId('date-range-picker-modal'), 'Cancel closes it').toHaveCount(0);
    await expect(
      page.getByTestId('timeline-reset-button'),
      'a cancelled picker changed nothing'
    ).toHaveCount(0);

    /* ── a committed range that legitimately holds none of the fixture. This door
         does NOT truncate (EventTimeline.tsx:1134-1140 writes the pair verbatim),
         so the server sees exactly the pair typed. ── */
    await page.getByTestId('custom-range-button').click();
    await page.getByTestId('start-date-input').fill('2020-01-01');
    await page.getByTestId('end-date-input').fill('2020-01-31');
    await expect(page.getByTestId('date-range-apply'), 'a valid pair enables Apply').toBeEnabled();
    const filtered = page.waitForRequest(
      (r) =>
        r.url().includes('timeline-summary') &&
        new URL(r.url()).searchParams.get('start_date') === '2020-01-01',
      { timeout: 20_000 }
    );
    await page.getByTestId('date-range-apply').click();
    await expect(page.getByTestId('date-range-picker-modal'), 'Apply closes the modal').toHaveCount(
      0
    );
    const params = new URL((await filtered).url()).searchParams;
    expect(params.get('end_date'), 'this door sends the pair verbatim').toBe('2020-01-31');
    expect(params.get('bucket_size'), 'the zoom survives the pick').toBe('week');

    // The header reduce over the filtered buckets is the observable: a scrubber
    // that dropped the filter could not reach zero.
    await expect(
      headerLine(page, 0),
      "the 2020 range reached the scrubber's own query"
    ).toBeVisible();
    // And the strip follows the returned buckets — asserted against the server's
    // answer for the SAME dated window, so it holds on any clock.
    const empty2020 = await summary(session, 'week', '&start_date=2020-01-01&end_date=2020-01-31');
    await expect(bars, "the strip redraws over the filtered window's buckets").toHaveCount(
      empty2020.buckets.length
    );
    expect(
      empty2020.buckets.every((b) => b.event_count === 0),
      'a 2020 window genuinely holds none of the fixture'
    ).toBe(true);

    await page.getByTestId('timeline-reset-button').click();
    await expect(
      headerLine(page, FIXTURE_ROWS.length),
      'Reset restores the unfiltered window'
    ).toBeVisible();
    await expect(bars, 'and the week strip with it').toHaveCount(WEEK_BARS);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('drags a range across bars; a drag inside one bucket sets nothing and neither moves the selection', async ({
    page,
  }) => {
    const session = await adminSession(harness);
    const truth = await summary(session, 'day');
    // Both ends of the drag sit hours from the fixture (rows are ~100 min old in a
    // 24 h window), so they are empty on any clock and the drag can only
    // demonstrate the filter round trip, never a count change. Emptiness is
    // re-checked against the RENDER below, because the window slides and an index
    // is only meaningful for the pixels it was read from.
    const START = 1;
    const END = 6;

    await boot(page);
    const strip = page.getByTestId('timeline-bars-container');
    await expect(strip, 'the strip is one drag/keyboard target').toHaveCount(1);
    await expect(strip).toHaveAttribute('role', 'slider');
    await expect(
      strip,
      'the selection indicator starts at bucket 0 (useState(0), :253)'
    ).toHaveAttribute('aria-valuenow', '0');

    /* Preconditions RESTATED AGAINST THE RENDER. The reads above happen seconds
     * before the strip is drawn, and the window slides with the clock
     * (`now - 24 h → now`, events.py:744-747), so a bucket's INDEX can shift by one
     * if the window crosses a bucket edge in between — and every gesture below
     * presses BY INDEX. `data-bucket-index` is the component's own map index
     * (:199), so this ties the aim to the pixels rather than to a stale array. */
    const drawn = await readBars(page);
    expect(drawn.length, 'the strip drew one bar per bucket').toBe(DAY_BARS);
    const countAt = (i: number): number => {
      const row = drawn.find((b) => b.index === i);
      if (!row) throw new Error(`no bar rendered for bucket ${i}`);
      return row.count;
    };
    expect(countAt(START), 'the aimed drag START is empty on screen').toBe(0);
    expect(countAt(END), 'the aimed drag END is empty on screen').toBe(0);
    const tallest = drawn.reduce((best, b) => (b.count > best.count ? b : best), drawn[0]);
    expect(tallest.count, 'the tallest bar holds the whole fixture').toBe(FIXTURE_ROWS.length);

    /* MEASURED INSTRUMENT DEFECT #4, and the one that makes the control below
     * mean anything: `page.mouse.move(x, y)` dispatches RAW VIEWPORT coordinates
     * and never scrolls, while `boundingBox()` will happily report a box below the
     * fold. On this boot the camera chip pushes the strip down, the press landed
     * in empty space below it, `handleMouseDown` never ran, and the real drag failed as a bare
     * 20 s waitForRequest timeout. Worse, the SAME mistake would have made the
     * negative control VACUOUS in the other direction — nothing lands, so nothing
     * is dispatched, so "the guard suppressed it" passes for the wrong reason.
     * A guard test that cannot tell "suppressed" from "never pressed" is not a
     * witness. Fix: scroll into view, measure after the scroll, and pair every
     * negative control with a positive twin in the same bucket. */
    /** Scroll the strip into view THEN measure — the order matters, and this is
     *  re-called after every reload because a reload can move the layout again. */
    async function geometry() {
      await strip.scrollIntoViewIfNeeded();
      const b = await strip.boundingBox();
      if (!b) throw new Error('the bars container has no box to drag over');
      /** Viewport y a few px below the strip's TOP edge. Bars are `flex-1` and fill
       *  the 64 px strip, so any y inside the container is over a bar, and staying
       *  near the top keeps the pointer inside the container if a hover tooltip or
       *  a layout nudge moves the box a little. */
      const overStrip = b.y + Math.min(8, b.height / 2);
      return {
        /** A viewport point the shipped handler resolves to bucket i: it reads x
         *  against `getBoundingClientRect()` of the container, so restate its own
         *  formula rather than invent one. */
        pointIn: (i: number): { x: number; y: number } => ({
          x: b.x + (b.width * (i + 0.5)) / DAY_BARS,
          y: overStrip,
        }),
        /** The bucket the handler says a viewport x lands in. */
        bucketAt: (x: number): number =>
          Math.min(DAY_BARS - 1, Math.max(0, Math.floor(((x - b.x) / b.width) * DAY_BARS))),
      };
    }
    let geo = await geometry();

    /* NEGATIVE CONTROL for the shipped guard: down and up inside ONE bucket must
     * dispatch nothing (`if (startIndex !== finalEndIndex)`, :437). MEASURED, this
     * control was first written as `expect(reset).toHaveCount(0)` and that is NOT a
     * witness: a round trip can land after the check, so a build that dispatches on
     * every mouseup passes it — proven by deleting the guard, which this file only
     * failed LATER (the collapsed window, not this line). The control therefore
     * OBSERVES the network from install to a settled reload, and asserts two things
     * together: that it saw summary requests at all (a dead listener cannot satisfy
     * that), and that not one of them carried a date.
     * POSITIVE TWIN: the same gesture on a bar that HAS events must set the filter,
     * so the file proves the press landed before it credits the suppression. Its
     * own bucket index is read back through the shipped formula and required to
     * equal the bucket aimed at — a pointer that slid off the strip fails HERE,
     * where the message names the problem, instead of surfacing as a timeout two
     * statements later. */
    const summaryDates: Array<string | null> = [];
    page.on('request', (r) => {
      if (new URL(r.url()).pathname === '/api/events/timeline-summary') {
        summaryDates.push(new URL(r.url()).searchParams.get('start_date'));
      }
    });

    /* --- POSITIVE TWIN. Press and release inside ONE bucket on the TALLEST bar.
     * The bar is a <button> whose height is its FILL (`max(4%, count/max)`, :193)
     * inside a `flex h-full items-end` wrapper, so only a max-count bar covers the
     * whole strip: pressing near the top of that column is over the button, its DOM
     * `click` fires, and `handleBarClick` (:326) sets the filter. That is what makes
     * "nothing was dispatched" below evidence about the guard rather than about a
     * pointer that missed the strip. */
    const filled = tallest.index;
    expect(filled, 'the tallest bar is a real bucket index').toBeGreaterThanOrEqual(0);
    const pIn = geo.pointIn(filled);
    expect(geo.bucketAt(pIn.x), 'the twin pointer is where the handler reads it').toBe(filled);
    const twin = page.waitForRequest(
      (r) =>
        r.url().includes('/api/events/timeline-summary') &&
        new URL(r.url()).searchParams.has('start_date'),
      { timeout: 20_000 }
    );
    await page.mouse.move(pIn.x, pIn.y);
    await page.mouse.down();
    await page.mouse.up();
    await twin;
    await expect(
      page.getByTestId('timeline-reset-button'),
      'the positive twin set a filter, so a press on this strip is observable'
    ).toBeVisible();
    await page.getByTestId('timeline-reset-button').click();
    await expect(
      page.getByTestId('timeline-bar'),
      'and Reset cleared it back to the full strip'
    ).toHaveCount(DAY_BARS);
    // The twin's own dated request is in the collector; the control below asserts
    // the collector holds NO dates, so start its window here.
    summaryDates.length = 0;
    // Removing the range chip moves the strip — re-measure before pressing again.
    geo = await geometry();

    /* --- NEGATIVE CONTROL, same gesture one bucket over, where the bar is 4 % tall
     * at the strip's bottom: near the top the pointer is over the CONTAINER, so the
     * button's click cannot fire and the only path left is the container's own
     * mousedown/mouseup pair, which is what :437 guards. */
    const pOut = geo.pointIn(START);
    expect(geo.bucketAt(pOut.x), 'the control pointer is in the aimed empty bucket').toBe(START);
    expect(countAt(geo.bucketAt(pOut.x)), 'and that bucket is empty on screen').toBe(0);
    /* The selection to compare against. It is NOT necessarily '0' any more: the
     * positive twin above pressed a bar, and `handleBarClick` DOES call
     * setSelectedIndex (:340). The claim this line makes is "a drag does not MOVE
     * the selection", so it keys on the value actually on screen. Reading it before
     * the reload matters too — a reload resets useState(0) (:253) and would make
     * any post-reload comparison vacuous. The "starts at 0" half of the claim is
     * asserted at the top of this test, on a fresh boot, where it is meaningful. */
    const selectionBefore = await strip.getAttribute('aria-valuenow');
    if (selectionBefore === null) throw new Error('the slider has no aria-valuenow to compare');
    await page.mouse.move(pOut.x, pOut.y);
    await page.mouse.down();
    await page.mouse.up();
    await expect(
      strip,
      'a mouseup moves no selection (only click/keys call setSelectedIndex)'
    ).toHaveAttribute('aria-valuenow', selectionBefore);
    await settledReload(page); // settle the round trip, and prove the listener is live
    expect(
      summaryDates.length,
      'the control saw summary requests — so "none of them filtered" is an observation'
    ).toBeGreaterThan(0);
    expect(
      summaryDates.filter((d) => d !== null),
      'a same-bucket drag set no date filter (the :437 guard)'
    ).toEqual([]);

    /* The drag's OWN precondition, watched. handleMouseDown returns early when
     * `buckets.length === 0` (:366) — it sets no state and logs nothing, so a
     * mousedown landing while the reloaded strip is still empty starts NO drag,
     * and the only symptom is a timeout on a request that never comes. The control
     * above ends in a reload, so wait for the strip and re-measure its box. */
    await expect(
      page.getByTestId('timeline-bar'),
      'the strip is drawn again after the control reload, so the drag has bars to press'
    ).toHaveCount(DAY_BARS);
    geo = await geometry();
    const pStart = geo.pointIn(START);
    const pEnd = geo.pointIn(END);
    expect(geo.bucketAt(pStart.x), 'drag anchor resolves to the aimed bucket').toBe(START);
    expect(geo.bucketAt(pEnd.x), 'drag release resolves to the aimed bucket').toBe(END);

    /* A real drag: bucket 1 → bucket 6. handleMouseUp emits
     * {start: buckets[1].timestamp, end: buckets[6].timestamp + 1 h} and the page
     * day-truncates both (:1125-1126). Whether those two dates are the SAME
     * calendar day depends on where the sliding 24 h window sits relative to UTC
     * midnight, so the bar-count claim is made against the server's answer for
     * the params the page ACTUALLY SENT, not against a hardcoded number. */
    const dragged = page.waitForRequest(
      (r) =>
        r.url().includes('/api/events/timeline-summary') &&
        new URL(r.url()).searchParams.has('start_date'),
      { timeout: 20_000 }
    );
    await page.mouse.move(pStart.x, pStart.y);
    await page.mouse.down();
    await page.mouse.move(pEnd.x, pEnd.y, { steps: 6 });
    await page.mouse.up();
    const params = new URL((await dragged).url()).searchParams;
    /* Which day the drag should have sent, WITHOUT pretending the window is
     * static: the unfiltered window is `now - 24 h → now` (events.py:744-747), so
     * bucket START's own timestamp slides. The page's render is bracketed by the
     * read taken before the boot and this one after the drag, and its bucket START
     * can only be a day inside that bracket — usually ONE value, two at worst (the
     * seconds either side of UTC midnight). Anything else — the raw ISO instant
     * (truncation removed), the END bucket's day, or no date at all — fails. */
    const after = await summary(session, 'day');
    const bracketDays = new Set<string>();
    for (const b of [...truth.buckets, ...after.buckets])
      bracketDays.add(b.timestamp.split('T')[0]);
    // (Array receiver, so a null start_date fails as "absent" rather than reading
    // as a substring test against a Set.)
    expect(
      Array.from(bracketDays),
      'the drag set a DAY-TRUNCATED start_date inside the window it was drawn from'
    ).toContain(params.get('start_date'));

    await expect(
      page.getByTestId('timeline-reset-button'),
      'the drag activated the custom range'
    ).toBeVisible();
    const draggedWindow = await summary(
      session,
      'day',
      `&start_date=${params.get('start_date')}&end_date=${params.get('end_date')}`
    );
    await expect(
      page.getByTestId('timeline-bar'),
      'the strip redraws over exactly the window the drag asked for'
    ).toHaveCount(draggedWindow.buckets.length);
    await expect(
      strip,
      'the drag never touches the selection indicator (only click/keys do)'
    ).toHaveAttribute('aria-valuenow', '0');

    await page.getByTestId('timeline-reset-button').click();
    await expect(page.getByTestId('timeline-bar'), 'Reset returns the full strip').toHaveCount(
      DAY_BARS
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
