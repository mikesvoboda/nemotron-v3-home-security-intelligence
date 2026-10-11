/**
 * F2.3 DO-1 golden path, alerts half (inventory F-077 + F-080; claim #6996).
 *
 * Drops the batch fixture (slow-reply.jpg — harness.ts explains why DO-1
 * claims that scenario), waits for the fake VLM's verdict through the real
 * pipeline, then drives /alerts unmocked: severity summary, severity filter
 * (including the band-pinned empty state), grouped/grid toggle, the
 * infinite-scroll end marker, refresh, and the shared EventDetailModal opened
 * through the page's own click path — content, its lazy detections leg, and a
 * REAL prev/next navigation.
 *
 * Why prev/next is real here: golden only runs after the harness's own smoke()
 * passed (scripts/feature_check.py run order), and smoke dropped
 * harness-smoke.jpg — score 61, also the `high` band (severity.py defaults
 * 29/59/84). So /alerts shows exactly two alerts, in two camera groups. The
 * grid sorts by severity rank, then newest first (AlertsPage sortedAlerts),
 * and smoke's event is always older than this drop, so position 2 is THIS
 * event; from there Previous must land on the smoke event and Next must walk
 * back. Both orders are pinned from the API, not assumed.
 */
import { expect, test } from '../guard';
import {
  adminSession,
  assertEventOnAlerts,
  assertGuardSurvives,
  assertStoredDetections,
  authedFetch,
  awaitVerdictedEvents,
  dropDo1Fixture,
  login,
  readHarness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

// The harness's own smoke scenario (harness-smoke.jpg, score 61) always lands
// on the stack before golden runs — its event is the second alert this spec
// navigates to. Its presence is asserted in the test body via the high list;
// this spec never drops that fixture.

test.describe('DO-1 golden path: /alerts severity surfaces and event detail @critical', () => {
  test.setTimeout(240_000); // slow-reply's 40 s delay + 150 s poll budget + page drives

  test('a high-risk drop surfaces on /alerts with band-correct chrome, and its detail round-trips', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    // 1. The drop, through O2.2's own helper (documented contract, as
    //    dashboard-drop.spec.ts does).
    dropDo1Fixture(h);

    // 2. Backend first: /alerts can only honestly list an event that is
    //    provably in the store. Assert the page's own listing predicate
    //    (useAlertsQuery pages fetchEvents({risk_level})) before any UI.
    const session = await adminSession(h);
    const api = authedFetch(h, session);
    const items = await awaitVerdictedEvents(h, api, 190_000); // 150 s proven + 40 s delay
    const eventId = assertEventOnAlerts(items, h);
    assertStoredDetections(items, h);
    const highList = await api.getJson('/api/events?risk_level=high');
    expect(highList.status, 'the risk_level filter answers').toBe(200);
    const high = (highList.body?.items ?? []) as Record<string, any>[];
    const highIds = high.map((e) => String(e.id));
    expect(highIds, 'the event is on the high page /alerts reads').toContain(eventId);

    // The grid order this spec navigates by, pinned from the API: exactly two
    // high alerts (this drop + the older smoke event), both high, so
    // sortedAlerts (severity rank, then newest first) must list THIS event at
    // index 1 and the smoke event at index 0.
    expect(high.length, 'this stack carries the drop plus the smoke event').toBe(2);
    const byNewest = [...high].sort(
      (a, b) => new Date(String(b.started_at)).getTime() - new Date(String(a.started_at)).getTime()
    );
    expect(String(byNewest[0].id), 'the drop is the newest high alert').toBe(eventId);
    const smokeEventId = String(byNewest[1].id);
    expect(
      String(byNewest[1].camera_id),
      'the older high alert is the harness smoke camera'
    ).not.toBe(h.cameraId);

    // 3. /alerts chrome (F-077), unmocked.
    await login(page, h, session);
    await page.goto(`${h.ui}/alerts`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('alerts-page')).toBeVisible({ timeout: 30_000 });

    // The severity summary appears only with alerts.length > 0; buckets render
    // per non-zero level, so the High bucket must show and Critical must not
    // (nothing on a fresh stack scores above high_max=84).
    const summary = page.getByTestId('alert-severity-summary');
    await expect(summary, 'the high events produce a severity summary').toBeVisible();
    await expect(summary.getByText('High', { exact: true })).toBeVisible();
    await expect(summary.getByText('Critical', { exact: true })).toHaveCount(0);

    // Grouped-by-camera view: both cameras get a group, each carrying its own
    // book summary (the drop's camera proves the group is real data, not chrome).
    const group = page.getByTestId(`alert-camera-group-${h.cameraId}`);
    await expect(group, 'the alert groups under its camera').toBeVisible();
    await expect(group).toContainText(h.scenario.verdict.summary);
    await expect(page.getByTestId('alerts-grouped-view')).toContainText('2 alerts');

    // Severity filter → Critical Only must EMPTY to the band truth, and the
    // empty-state copy names the filter it found nothing for.
    await page.locator('#risk-filter').selectOption('critical');
    await expect(
      page.getByText('There are no critical risk events to review.'),
      'the high events stay off the critical page — the 29/59/84 bands hold end to end'
    ).toBeVisible({ timeout: 15_000 });
    await page.locator('#risk-filter').selectOption('all');
    await expect(group, 'All restores the alerts').toBeVisible({ timeout: 15_000 });

    // Grid view: both events through EventCard, newest (this drop) second per
    // the order pinned above, plus the infinite-scroll sentinel reporting the
    // end of the list (one page).
    await page.getByLabel('Grid view').click();
    const grid = page.getByTestId('alerts-grid-view');
    await expect(grid).toBeVisible();
    const cards = grid.locator('[data-testid^="event-card-"]');
    await expect(cards, 'both high alerts list in the grid').toHaveCount(2);
    await expect(cards.nth(0), 'grid order: oldest high first').toHaveAttribute(
      'data-testid',
      `event-card-${smokeEventId}`
    );
    await expect(cards.nth(1), 'grid order: the newest high alert is second').toHaveAttribute(
      'data-testid',
      `event-card-${eventId}`
    );
    await expect(page.getByText('All alerts loaded')).toBeVisible();

    // 4. Event detail through the grid card's OWN click path (F-080):
    //    EventCard onClick → setSelectedEventForModal → shared
    //    EventDetailModal. The modal's detections ride a lazy
    //    GET /api/events/<id>/detections — observe (not intercept; the guard
    //    would reject a stub) that it answers with the stored detection.
    const detectionsResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === `/api/events/${eventId}/detections`,
      { timeout: 20_000 }
    );
    await page.getByTestId(`event-card-${eventId}`).click();
    const modal = page.getByTestId('event-detail-modal');
    await expect(modal, 'the alert click opened the shared detail modal').toBeVisible({
      timeout: 15_000,
    });
    const detResp = await detectionsResponse;
    expect(detResp.status(), 'the modal detections endpoint answers').toBe(200);
    const detBody = await detResp.json().catch(() => null);
    const stored = Array.isArray(detBody)
      ? detBody
      : ((detBody?.detections ?? detBody?.items ?? []) as unknown[]);
    expect(
      stored.length,
      'the modal loads the stored detection, not an empty list'
    ).toBeGreaterThanOrEqual(1);

    await expect(page.getByTestId('risk-score')).toContainText(
      String(h.scenario.verdict.risk_score)
    );
    await expect(page.getByTestId('ai-analysis-section')).toContainText(h.scenario.verdict.summary);
    await expect(page.getByTestId('detection-camera')).toContainText(h.scenario.name);

    // 5. REAL prev/next (F-080): from this event, Previous must land on the
    //    smoke event — its score (61) differs from this one (70), so the swap
    //    is observable without touching camera internals — and Next walks back.
    //    The keyboard path (ArrowLeft/ArrowRight) must agree.
    await modal.getByRole('button', { name: 'Previous event' }).click();
    await expect(
      page.getByTestId('risk-score'),
      'Previous navigates to the smoke event (score 61)'
    ).toContainText('61', { timeout: 15_000 });
    await modal.getByRole('button', { name: 'Next event' }).click();
    await expect(page.getByTestId('risk-score')).toContainText(
      String(h.scenario.verdict.risk_score)
    );
    await page.keyboard.press('ArrowLeft');
    await expect(
      page.getByTestId('risk-score'),
      'ArrowLeft navigates like the button'
    ).toContainText('61');
    await page.keyboard.press('ArrowRight');
    await expect(page.getByTestId('risk-score')).toContainText(
      String(h.scenario.verdict.risk_score)
    );

    // 6. Close through the modal's own button; grouped chrome intact (toggle
    //    back proves the page survived the navigation).
    await page.getByTestId('close-modal-button').click();
    await expect(modal).toBeHidden({ timeout: 10_000 });
    await page.getByLabel('Group by camera').click();
    await expect(page.getByTestId('alerts-grouped-view')).toBeVisible();
    await expect(group).toBeVisible();

    // 7. End-to-end honesty: still the harness's UI; guard survived the drive.
    await assertGuardSurvives(page, h);
  });
});
