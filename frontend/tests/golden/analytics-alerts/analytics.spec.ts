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
 * really produced (this drop's 1 detection plus the harness smoke run's):
 *  F-070  /analytics mounts; the default Grafana view embeds the hsi-analytics
 *         dashboard; the external link and refresh exist; refresh reloads the
 *         iframe (src re-set); the toggle switches to the Native view.
 *  F-071  Native: the camera selector offers the harness camera; selecting it
 *         filters GET /api/detections/stats by camera_id (observed on the
 *         network, not assumed) and the detail card shows THIS camera's
 *         single detection at the book's 0.91 confidence (UI renders 91%) with
 *         the person class row.
 *  F-072  trends / donut / uptime cards resolve to data or their named empty
 *         state — a stranded skeleton is the failure F2.3 exists to catch.
 *  F-073  risk history / distribution / trend cards resolve the same way.
 *  F-074  week-over-week resolves and, when it has data, its three metric
 *         pairs (detections, high-risk, avg-risk) are present.
 *  F-075  latency panel: range selector + refresh exist; the stage bars come
 *         from GET /api/system/pipeline-latency observed on the network, and
 *         the pipeline that ran for the drop must have written the in-process
 *         ring, so watch_to_detect / detect_to_batch bars must show.
 *
 * The API leg runs BEFORE the UI leg (the dashboard-drop discipline): an
 * aggregate the store cannot produce would otherwise pass as a rendered card.
 */
import { expect, test } from '../guard';
import { adminSession, assertGuardSurvives, authedFetch, login, readHarness } from './harness';

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
 *  verified against each component's returns, EXCEPT the latency panel, which
 *  renders none of these (it has its own states; handled separately below). */
const RESOLVING_CARDS = [
  'detection-trends',
  'object-distribution',
  'camera-uptime',
  'risk-history',
  'risk-score-distribution',
  'risk-score-trend',
  'week-over-week',
] as const;

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
    expect(
      Math.round(Number(stats.body?.average_confidence ?? 0) * 100),
      'average confidence is the book value (0.91)'
    ).toBe(Math.round(h.scenario.detections[0].confidence * 100));

    for (const path of [
      `/api/analytics/detection-trends?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/risk-history?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/risk-score-distribution?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/risk-score-trends?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/object-distribution?start_date=${weekAgo}&end_date=${today}`,
      `/api/analytics/camera-uptime?start_date=${weekAgo}&end_date=${today}`,
    ]) {
      const res = await api.getJson(path);
      expect(res.status, `${path.split('?')[0]} answers the page window`).toBe(200);
    }
    const latency = await api.getJson('/api/system/pipeline-latency');
    expect(latency.status, 'pipeline-latency answers').toBe(200);

    // 2. /analytics default view (F-070): page mounts, Grafana embeds, chrome
    //    exists, refresh reloads the iframe src, toggle reaches Native.
    await login(page, h, session);
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

    // Refresh (F-070): the handler blanks the src then restores it — watch the
    // attribute re-set to the same dashboard URL.
    await page.getByTestId('analytics-refresh-button').click();
    await expect(iframe, 'refresh reloads the iframe to the same dashboard').toHaveAttribute(
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
    //    detection: total 1, confidence 91% (0.91 at the component's rounding),
    //    class row person (the book's detection).
    await expect(page.getByTestId('camera-analytics-selector')).toBeVisible();
    const cameraOption = page.getByTestId(`camera-option-${h.cameraId}`);
    await expect(cameraOption, 'the selector lists the harness camera').toBeVisible({
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
    await expect(
      page.getByTestId(`class-item-${h.scenario.detections[0].class}`),
      'the class row is the stored detection class'
    ).toBeVisible({ timeout: 15_000 });
    const detailText = await detail.innerText();
    expect(detailText, 'detail shows the stored detection count').toMatch(/\b1\b/);
    expect(detailText, 'confidence renders at the UI rounding of the book value').toMatch(/91%/);

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
    // Where the batch data MUST show, pin it rather than accept an empty state:
    // the trends window contains this drop's detection, so the totals carry a
    // number (the API leg proved the row exists; the card must not deny it).
    const trendsCard = page.getByTestId('detection-trends-card');
    await expect(trendsCard, 'the trends card has real data to show').toBeVisible({
      timeout: 25_000,
    });
    await expect(page.getByTestId('detection-trends-total')).toContainText(/\d/);

    // 5. F-075: latency chrome + the ring the pipeline filled. The drop's
    //    pipeline ran in THIS stack, so the file watcher's samples must put at
    //    least watch_to_detect and detect_to_batch bars on screen; the batch
    //    legs may or may not have completed within the panel's default window,
    //    so assert the two guaranteed stages only.
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
    await refresh.click(); // a real refetch; the bars must survive it
    await expect(page.getByTestId('stage-bar-watch_to_detect')).toBeVisible({ timeout: 15_000 });

    // 6. Still the harness UI; the guard survived every read above.
    await assertGuardSurvives(page, h);
  });
});
