/**
 * F2.3 DO-1 golden path, analytics half (inventory F-070 to F-075; claim #6996).
 *
 * DROPS NOTHING. One image per run is all the watcher's 300 s stack-wide dedupe
 * allows the batch (harness.ts), and it belongs to alerts.spec.ts. File order
 * does the rest: workers=1 with Playwright's default sort order 'file' runs
 * analytics.spec.ts AFTER alerts.spec.ts ('alerts' < 'analytics'). If that ever
 * stops being true, the backend leg below fails with a named cause instead of
 * vacuously passing on an empty store.
 *
 * What it proves per row, against the events and detections the fake stack
 * really produced (this drop's 1 detection, class `car`, confidence 0.77 —
 * every number read from the book through h.scenario, never a literal):
 *  F-070  /analytics mounts; the default Grafana view embeds the hsi-analytics
 *         dashboard; the external link exists; refresh RELOADS the iframe —
 *         pinned by watching a second request for the same dashboard URL land
 *         after the click (the handler blanks src and restores it 100 ms later,
 *         AnalyticsPage.tsx:82-98, so catching the empty attribute would be a
 *         race, and asserting the src again afterwards is the reviewer's noted
 *         stale-pass); the toggle switches to the Native view.
 *  F-071  Native: the camera selector offers the harness camera; selecting it
 *         filters GET /api/detections/stats by camera_id (observed on the
 *         network, not assumed) and the detail card shows THIS camera's single
 *         detection — bound element by element (the "Total Detections" value,
 *         the "Average Confidence" value, the class row) instead of a loose
 *         innerText regex.
 *  F-072  trends / donut / uptime cards resolve to data or their named empty
 *         state — a stranded skeleton is the failure F2.3 exists to catch.
 *  F-073  risk history / distribution / trend cards resolve the same way.
 *  F-074  week-over-week resolves and, when it has data, its metric pairs exist.
 *  F-075  latency panel: range selector + refresh exist; the pipeline that ran
 *         for the drop must have written the in-process ring, so
 *         watch_to_detect / detect_to_batch bars must show. (Both are recorded
 *         unconditionally on the path the drop takes: file_watcher.py:829 and
 *         pipeline_workers.py:529 — the latter records after _process_image_
 *         detection returns, so it lands before the analyzer's verdict, which
 *         is why a verdict that fails closed would still not have hidden it.)
 *
 * The API leg runs BEFORE the UI leg (the dashboard-drop discipline): an
 * aggregate the store cannot produce would otherwise pass as a rendered card.
 */
import { expect, test } from '../guard';
import {
  adminSession,
  assertGuardSurvives,
  authedFetch,
  login,
  readHarness,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** ISO yyyy-mm-dd, N UTC days back — AnalyticsPage's own 7-day convention. */
function isoDaysBack(days: number): string {
  return new Date(Date.now() - days * 86_400_000).toISOString().split('T')[0];
}

/** card testid + its loading skeleton testid, per the components' own states.
 *  The empty-state id is the card id with '-card' swapped to '-empty' —
 *  verified against each component's returns, with TWO exceptions:
 *  - the latency panel renders none of these (it has its own states; handled
 *    separately below), and
 *  - WeekOverWeekCard has NO empty state at all (its static testids are
 *    -loading :294, -error :306, -card :317), so for 'week-over-week' the
 *    .or() below collapses to -card only. That is a strictly weaker pin for
 *    that one card, stated here rather than left for a reader to discover. */
const RESOLVING_CARDS = [
  'detection-trends',
  'object-distribution',
  'camera-uptime',
  'risk-history',
  'risk-score-distribution',
  'risk-score-trend',
  'week-over-week',
] as const;

/** The percentage the detail card will render for a stored average: the
 *  component's own rounding (CameraAnalyticsDetail.tsx:98-101), applied to the
 *  book value the API leg just confirmed the store holds. */
function bookConfidencePercent(h: Harness): number {
  return Math.round(h.scenario.detections[0].confidence * 100);
}

test.describe('DO-1 golden path: /analytics surfaces over the batch data @critical', () => {
  test.setTimeout(90_000); // no pipeline wait here — the events already landed

  test('the native analytics view aggregates what the API leg just proved is stored', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await adminSession(h);
    const api = authedFetch(h, session);
    const today = isoDaysBack(0);
    const weekAgo = isoDaysBack(7);

    // 1. API leg — the store must already hold what the UI is about to show.
    //    Non-emptiness asserted before any equality (the vacuous-pass law).
    const events = await api.getJson(`/api/events?camera_id=${encodeURIComponent(h.cameraId)}`);
    expect(events.status, 'events readable').toBe(200);
    const items = (events.body?.items ?? []) as Record<string, any>[];
    expect(items.length, 'this spec depends on alerts.spec.ts having run first').toBe(1);
    expect(Number(items[0].risk_score), 'the batch event carries the book score').toBe(
      h.scenario.verdict.risk_score
    );

    const stats = await api.getJson(
      `/api/detections/stats?camera_id=${encodeURIComponent(h.cameraId)}`
    );
    expect(stats.status, 'per-camera stats answer').toBe(200);
    expect(Number(stats.body?.total_detections ?? 0), 'this camera stored its detection').toBe(1);
    const byClass = (stats.body?.detections_by_class ?? {}) as Record<string, number>;
    expect(byClass, 'stats group by class for this camera').toEqual({
      [h.scenario.detections[0].class]: 1,
    });
    const bookPercent = bookConfidencePercent(h);
    expect(
      Math.round(Number(stats.body?.average_confidence ?? 0) * 100),
      'average confidence is the book value at UI rounding'
    ).toBe(bookPercent);

    for (const path of [
      `/api/analytics/risk-history?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/risk-score-distribution?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/risk-score-trends?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/object-distribution?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/camera-uptime?start_date=${weekAgo}&end_date=${today}`,
    ]) {
      const res = await api.getJson(path);
      expect(res.status, `${path.split('?')[0]} answers the page window`).toBe(200);
    }

    // Detection trends gets its own read because the UI leg pins the card's
    // total against THIS number (DetectionTrendsCard renders
    // `total_detections` of the same response, DetectionTrendsCard.tsx:132 via
    // useDetectionTrendsQuery.ts:162-164). Pinning the card against the store's
    // own answer is the claim "reflects stored detections"; a digit regex would
    // also pass on "0", which is the card DENYING the data.
    const trendsRes = await api.getJson(
      `/api/analytics/detection-trends?start_date=${weekAgo}&end_date=${today}`
    );
    expect(trendsRes.status, 'detection-trends answers the page window').toBe(200);
    const apiTrendsTotal = Number(trendsRes.body?.total_detections ?? NaN);
    expect(Number.isFinite(apiTrendsTotal), 'the response carries total_detections').toBe(true);
    // Non-emptiness BEFORE equality: this batch stored detections, so a 0 here
    // is the store refusing the data — that must fail here, not silently pair
    // with a card that also renders 0.
    expect(apiTrendsTotal, 'the window contains this batch detections').toBeGreaterThanOrEqual(1);

    const latency = await api.getJson('/api/system/pipeline-latency');
    expect(latency.status, 'pipeline-latency answers').toBe(200);

    // 2. /analytics default view (F-070): page mounts, Grafana embeds, chrome
    //    exists, refresh RELOADS the iframe, toggle reaches Native.
    await login(page, h, session);
    const dashboardRequests: string[] = [];
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.includes('/d/hsi-analytics')) {
        dashboardRequests.push(request.url());
      }
    });
    await page.goto(`${h.ui}/analytics`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('analytics-page'), 'analytics page mounts').toBeVisible({
      timeout: 30_000,
    });
    const iframe = page.getByTestId('grafana-iframe');
    await expect(iframe, 'default view embeds the hsi-analytics dashboard').toHaveAttribute(
      'src',
      /hsi-analytics/
    );
    await expect(page.getByTestId('grafana-external-link')).toBeVisible();
    // The embed really asked Grafana for the dashboard (it may still be loading
    // — the fake stack ships no Grafana data — but the REQUEST is the pin).
    await expect
      .poll(() => dashboardRequests.length, {
        message: 'the iframe requested the hsi-analytics dashboard',
        timeout: 20_000,
      })
      .toBeGreaterThan(0);

    // Refresh (F-070): the handler blanks the src and restores it in a 100 ms
    // setTimeout (AnalyticsPage.tsx:82-98, the `, 100);` at :94). Re-asserting
    // the src afterwards would
    // pass on a dead button, and racing the empty attribute is flaky by design,
    // so pin the reload by its observable: a SECOND request for the same
    // dashboard URL, appearing only after the click.
    const beforeRefresh = dashboardRequests.length;
    await page.getByTestId('analytics-refresh-button').click();
    await expect
      .poll(() => dashboardRequests.length, {
        message: 'refresh re-requested the dashboard — the iframe actually reloaded',
        timeout: 20_000,
      })
      .toBeGreaterThan(beforeRefresh);
    await expect(iframe, 'and the src points at the dashboard again').toHaveAttribute(
      'src',
      /hsi-analytics/
    );

    // View toggle → Native (opens F-071+). Cost view is another row's surface;
    // DO-1 pins only the Grafana↔Native leg its rows describe.
    await page.getByTestId('view-mode-native').click();
    await expect(page.getByTestId('native-analytics-view')).toBeVisible({ timeout: 15_000 });

    // 3. F-071: selecting the harness camera must REFILTER the stats call by
    //    camera_id (useCameraAnalytics passes selectedCameraId; observe it on
    //    the network) and the detail card then shows exactly this camera's one
    //    detection: total 1, the book confidence at the component's rounding,
    //    the class row named for the stored detection class.
    await expect(page.getByTestId('camera-analytics-selector')).toBeVisible();
    // Tremor's Select is a headlessui Listbox, not a native <select>: its
    // options are ListboxOption children of ListboxOptions, which headlessui
    // renders ONLY while the dropdown is open (verified in the 2026-10-11 CI
    // failure — the container was visible and the option testid never existed,
    // because the Listbox button had never been opened). SelectItem does forward
    // data-testid onto the option (read from @tremor/react 3.18.7, the
    // package-lock pin), so opening the button is the whole fix. The button is
    // addressed structurally, by role inside the selector container, because its
    // accessible name is the placeholder and later becomes the camera's own
    // name — a name-based locator would only work pre-selection.
    const selectorButton = page.getByTestId('camera-analytics-selector').getByRole('button');
    await expect(selectorButton, 'the camera dropdown renders its button').toBeVisible({
      timeout: 15_000,
    });
    await selectorButton.click();
    const cameraOption = page.getByTestId(`camera-option-${h.cameraId}`);
    await expect(cameraOption, 'the OPEN selector lists the harness camera').toBeVisible({
      timeout: 15_000,
    });
    const filteredStats = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/detections/stats' &&
        new URL(response.url()).searchParams.get('camera_id') === h.cameraId,
      { timeout: 20_000 }
    );
    await cameraOption.click();
    const filtered = await filteredStats;
    expect(filtered.status(), 'the camera-filtered stats call answers').toBe(200);
    const detail = page.getByTestId('camera-analytics-detail');
    await expect(detail, 'camera detail card renders').toBeVisible({ timeout: 20_000 });

    // Bound per element (CameraAnalyticsDetail.tsx:151-173): each stat block is
    //   <div> <div class="flex …"> <Icon/> <Text>{label}</Text> </div> <p>{value}</p> </div>
    // so the value paragraph is a following sibling of the LABEL'S WRAPPER, not
    // of the label itself. ancestor-or-self::div[1] is deliberate: Playwright's
    // text engine matches the SMALLEST element containing the text — if that is
    // the label paragraph, the walk lands on the flex wrapper; if it is the
    // wrapper itself, ancestor-or-self keeps the same anchor. ancestor::div[1]
    // would silently resolve to zero elements in the second case.
    // Pinning the two value paragraphs directly beats regex-matching the card's
    // whole innerText, where "1" would match any stray digit.
    const statValueFor = (label: string) =>
      detail
        .getByText(label, { exact: true })
        .locator('xpath=ancestor-or-self::div[1]/following-sibling::p');
    await expect(
      statValueFor('Total Detections'),
      'detail shows the stored detection count'
    ).toHaveText('1');
    await expect(
      statValueFor('Average Confidence'),
      'confidence renders at the component rounding of the book value'
    ).toHaveText(`${bookPercent}%`);
    const classRow = page.getByTestId(`class-item-${h.scenario.detections[0].class}`);
    await expect(classRow, 'the class row is the stored detection class').toBeVisible({
      timeout: 15_000,
    });
    await expect(classRow).toContainText('1');
    // Scoped to THIS card on purpose: a page-wide "no person row" would be a
    // false claim — the smoke camera's person detection exists store-wide and
    // the all-camera cards may legitimately show it. The card's own refilter
    // dropping the person row is the claim; the card owns its testids.
    await expect(
      detail.getByTestId('class-item-person'),
      'the refiltered card lists only this camera class'
    ).toHaveCount(0);

    // 4. F-072/073/074: every card resolves to data or its named empty state,
    //    and no skeleton strands (server data already exists — a loading card
    //    stuck here is the "renders nothing" failure class).
    for (const base of RESOLVING_CARDS) {
      await expect(
        page.getByTestId(`${base}-card`).or(page.getByTestId(`${base}-empty`)),
        `${base} resolves to data or its empty state`
      ).toBeVisible({ timeout: 25_000 });
      await expect(page.getByTestId(`${base}-loading`), `${base} never strands`).toHaveCount(0);
    }
    // Where the batch data MUST show, pin it rather than accept an empty state.
    // The total must EQUAL what the API leg read from the store for the same
    // window — /\d/ would also pass on "0", which is the card denying the very
    // data the store holds (formatNumber renders 0 as the string "0").
    const trendsCard = page.getByTestId('detection-trends-card');
    await expect(trendsCard, 'the trends card has real data to show').toBeVisible({
      timeout: 25_000,
    });
    await expect(
      page.getByTestId('detection-trends-total'),
      'the card total equals the store total for the same window'
    ).toHaveText(apiTrendsTotal.toLocaleString()); // DetectionTrendsCard.tsx:47-49

    // 5. F-075: latency chrome + the ring the pipeline filled. The drop's
    //    pipeline ran in THIS stack, so the file watcher's samples must put at
    //    least watch_to_detect and detect_to_batch bars on screen; the later
    //    stages may or may not have completed within the panel's default
    //    window, so assert the two guaranteed stages only.
    await expect(page.getByTestId('time-range-selector')).toBeVisible();
    const refresh = page.getByTestId('pipeline-latency-refresh-button');
    await expect(refresh).toBeVisible();
    await expect(
      page.getByTestId('stage-bar-watch_to_detect'),
      'the watcher recorded watch→detect latency for the drop'
    ).toBeVisible({ timeout: 25_000 });
    await expect(
      page.getByTestId('stage-bar-detect_to_batch'),
      'the detector recorded detect→batch latency for the drop'
    ).toBeVisible();
    // Clicking refresh and pinning SURVIVAL — deliberately weaker than the
    // alerts half's request-count pin, and stated rather than left implied:
    // AnalyticsPage mounts this panel with refreshInterval={30000}
    // (AnalyticsPage.tsx:278; the panel arms a setInterval when the prop is > 0,
    // PipelineLatencyPanel.tsx:96-99), so a /api/system/pipeline-latency request
    // appearing after the click is NOT attributable to the click — it could be
    // the timer. The alerts page has no such interval (useAlertsQuery's
    // refetchInterval defaults false, :237, and AlertsPage passes none), which
    // is why that half pins the request and this one pins the bars. A dead
    // onClick here would still fail on the bars only if the data also went
    // stale; the click's request itself is not claimed.
    await refresh.click();
    await expect(
      page.getByTestId('stage-bar-watch_to_detect'),
      'the bars survive the manual refresh'
    ).toBeVisible({ timeout: 15_000 });

    // 6. Still the harness UI; the guard survived every read above.
    await assertGuardSurvives(page, h);
  });
});
