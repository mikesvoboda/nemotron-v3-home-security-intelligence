/**
 * F2.3 DO-1 golden path, alerts half (inventory F-077 + F-080; claim #6996).
 *
 * Drops car-in-driveway.jpg (harness.ts explains the claim and the tier
 * arithmetic) and pins the SEVERITY BAND end to end, which is what this page
 * is: /alerts pages only `high` and `critical` (useAlertsQuery fetches exactly
 * those two risk levels), so
 *
 *   - the drop (uncertain, risk 45 → `medium`) must be IN the store and
 *     ABSENT from /alerts. The presence half is pinned first — a
 *     `risk_level=medium` read returns it — so the absence is the filter
 *     working, not the pipeline losing the event. An absence claim with no
 *     present control proves nothing.
 *   - the one alert the page shows is the harness's own smoke event
 *     (harness-smoke.jpg, risk 61 → `high`), dropped by feature_check.py's
 *     smoke() before golden starts (measured in the 2026-10-11 CI run: dropped
 *     07:42:18Z, golden launched 07:42:55Z). That is stack state this spec may
 *     rely on and must not re-create — re-dropping its bytes inside the
 *     watcher's 300 s sha256 window would just dedupe.
 *
 * Prev/next is therefore pinned as the shipped BOUNDS behaviour, not as
 * navigation: with exactly one alert, AlertsPage.handleNavigate computes
 * index-1 / index+1 and its `newIndex >= 0 && newIndex < alerts.length` guard
 * makes both a silent no-op, and EventDetailModal renders both buttons
 * unconditionally (no disabled state). That is the honest assertion for a
 * one-alert stack — real two-alert navigation needs a second `high` event,
 * which the shipped book cannot give a docs-owned spec (see the PR body's
 * harness ask). Pinning a no-op here is strictly better than a vacuous
 * count-equals-one check, and strictly worse than real navigation, which is
 * why the ask is filed rather than glossed.
 *
 * The grid order is not assumed: sortedAlerts sorts severity rank then newest
 * first (AlertsPage.tsx:125-134), so with one alert it is that alert — pinned
 * by testid, and the drop's card is pinned ABSENT.
 */
import { expect, test } from '../guard';
import {
  adminSession,
  assertDropEventStored,
  assertDropStoredItsDetection,
  assertGuardSurvives,
  assertSoleAlertIsSmoke,
  authedFetch,
  awaitVerdictedEvents,
  dropDo1Fixture,
  expectedTier,
  login,
  readHarness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

test.describe('DO-1 golden path: /alerts severity band, chrome and detail modal @critical', () => {
  test.setTimeout(200_000); // no reply delay on this scenario; 150 s proven poll + page drives

  test('a medium-risk drop stays off /alerts, the high harness alert carries its chrome, and the detail modal round-trips', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    // 1. The drop, through O2.2's own helper (documented contract, as
    //    dashboard-drop.spec.ts does).
    dropDo1Fixture(h);

    // 2. Backend first — the page's own listing predicate is
    //    fetchEvents({risk_level}) per level (useAlertsQuery), so the store is
    //    read on exactly those terms before any UI.
    const session = await adminSession(h);
    const api = authedFetch(h, session);
    const items = await awaitVerdictedEvents(h, api, 165_000);
    const dropEventId = assertDropEventStored(items, h);
    assertDropStoredItsDetection(items, h);

    // PRESENT control for every absence below: the drop is in the store and
    // tiered exactly where the book puts it, so /alerts hiding it is the filter.
    const dropTier = expectedTier(h.scenario.verdict.risk_score);
    const tierPage = await api.getJson(`/api/events?risk_level=${dropTier}`);
    expect(tierPage.status, `the ${dropTier} page answers`).toBe(200);
    const tierIds = ((tierPage.body?.items ?? []) as Record<string, any>[]).map((e) =>
      String(e.id)
    );
    expect(tierIds, 'the drop is listed by its own tier — the pipeline ran').toContain(dropEventId);

    // And the alert page the drive is built on: exactly one high/critical event.
    const highPage = await api.getJson('/api/events?risk_level=high');
    expect(highPage.status, 'the risk_level filter answers').toBe(200);
    const high = (highPage.body?.items ?? []) as Record<string, any>[];
    const alertId = assertSoleAlertIsSmoke(high, h, dropEventId);
    const criticalPage = await api.getJson('/api/events?risk_level=critical');
    const critical = (criticalPage.body?.items ?? []) as Record<string, any>[];
    expect(critical.length, 'nothing on this stack scores into critical').toBe(0);

    // 3. /alerts chrome (F-077), unmocked.
    await login(page, h, session);
    await page.goto(`${h.ui}/alerts`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('alerts-page')).toBeVisible({ timeout: 30_000 });

    // Severity summary renders a bucket only for a non-zero count, over the
    // LOADED alerts (AlertsPage riskCounts :113-123, buckets :391-425): so High
    // shows and Critical does not — and neither does Medium, which is the band
    // filter visible in the chrome even though the drop exists.
    const summary = page.getByTestId('alert-severity-summary');
    await expect(summary, 'the high alert produces a severity summary').toBeVisible();
    await expect(summary.getByText('High', { exact: true })).toBeVisible();
    await expect(summary.getByText('Critical', { exact: true })).toHaveCount(0);
    await expect(summary.getByText('Medium', { exact: true })).toHaveCount(0);

    // Page-level count line, outside the grouped container (AlertsPage.tsx:487):
    // the pluralization is driven by totalCount, so with one alert the copy is
    // singular — a real pin of that expression, not of a guessed string.
    await expect(
      page.getByText(`${high.length} alert${high.length === 1 ? '' : 's'} found`)
    ).toBeVisible();

    // Grouped view: the alert's OWN camera gets the group, and the group's
    // count line is per-camera ("1 alert", AlertCameraGroup.tsx:126/154),
    // default-expanded (:56). The drop's camera must get NO group at all.
    const alertGroup = page.getByTestId(`alert-camera-group-${h.smokeCameraId}`);
    await expect(alertGroup, 'the alert groups under its camera').toBeVisible();
    await expect(alertGroup.getByText('1 alert', { exact: true })).toBeVisible();
    await expect(
      alertGroup.getByText(h.smokeScenario.verdict.summary),
      'the group shows the stored verdict summary, not chrome'
    ).toBeVisible();
    await expect(
      page.getByTestId(`alert-camera-group-${h.cameraId}`),
      'the medium drop gets no camera group'
    ).toHaveCount(0);

    // Severity filter: Critical empties to the band truth and the empty-state
    // copy names the filter it found nothing for (AlertsPage.tsx:527).
    await page.locator('#risk-filter').selectOption('critical');
    await expect(
      page.getByText('There are no critical risk events to review.'),
      'the high alert stays off the critical page — the 29/59/84 bands hold end to end'
    ).toBeVisible({ timeout: 15_000 });

    // High filter must show it (the filter is not just "everything"), and All
    // restores the same one alert.
    await page.locator('#risk-filter').selectOption('high');
    await expect(alertGroup, 'the High filter lists the high alert').toBeVisible({
      timeout: 15_000,
    });
    await page.locator('#risk-filter').selectOption('all');
    await expect(alertGroup, 'All restores the alerts').toBeVisible({ timeout: 15_000 });

    // Refresh (F-077's "refreshes" clause): the button refetches
    // (AlertsPage.handleRefresh :350 → refetch()). Pin the click by what must
    // SURVIVE it, not by a spinner that may already be gone.
    await page.getByLabel('Refresh alerts').click();
    await expect(alertGroup, 'the alert survives the refresh').toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('alerts-grouped-view')).toBeVisible();

    // Grid view: one card, pinned by testid, and the drop's card absent. The
    // infinite-scroll sentinel reports the end of a one-page list.
    await page.getByLabel('Grid view').click();
    const grid = page.getByTestId('alerts-grid-view');
    await expect(grid).toBeVisible();
    const cards = grid.locator('[data-testid^="event-card-"]');
    await expect(cards, 'exactly the high alert lists in the grid').toHaveCount(1);
    await expect(cards.nth(0), 'the grid card is the high alert').toHaveAttribute(
      'data-testid',
      `event-card-${alertId}`
    );
    await expect(
      grid.locator(`[data-testid="event-card-${dropEventId}"]`),
      'the medium drop never reaches the grid'
    ).toHaveCount(0);
    await expect(page.getByText('All alerts loaded')).toBeVisible();

    // 4. Event detail through the grid card's OWN click path (F-080):
    //    EventCard onClick → setSelectedEventForModal → shared
    //    EventDetailModal. Its detections ride a lazy
    //    GET /api/events/<id>/detections — observe (not intercept; the guard
    //    would reject a stub) that it answers with the stored detection.
    const detectionsResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === `/api/events/${alertId}/detections`,
      { timeout: 20_000 }
    );
    await page.getByTestId(`event-card-${alertId}`).click();
    const modal = page.getByTestId('event-detail-modal');
    await expect(modal, 'the alert click opened the shared detail modal').toBeVisible({
      timeout: 15_000,
    });
    const detResp = await detectionsResponse;
    expect(detResp.status(), 'the modal detections endpoint answers').toBe(200);
    const detBody = await detResp.json().catch(() => null);
    // DetectionListResponse: {items: [...], pagination: {...}}
    const stored = Array.isArray(detBody)
      ? detBody
      : ((detBody?.items ?? detBody?.detections ?? []) as Record<string, any>[]);
    expect(stored.length, 'the modal loads the stored detection, not an empty list').toBe(
      h.smokeScenario.detections.length
    );
    expect(
      Math.round(Number(stored[0].confidence) * 100),
      'the stored confidence round-trips the book value at UI rounding'
    ).toBe(Math.round(h.smokeScenario.detections[0].confidence * 100));
    expect(String(stored[0].object_type), 'the stored detection carries the book class').toBe(
      h.smokeScenario.detections[0].class
    );

    await expect(page.getByTestId('risk-score')).toContainText(
      String(h.smokeScenario.verdict.risk_score)
    );
    await expect(page.getByTestId('ai-analysis-section')).toContainText(
      h.smokeScenario.verdict.summary
    );
    // detection-camera is the modal's title = the event's camera_name, which
    // AlertsPage resolves from /api/cameras; feature_check.py seeds each
    // camera with the scenario's own name (scripts/feature_check.py:1287).
    await expect(page.getByTestId('detection-camera')).toContainText(h.smokeScenario.name);

    // 5. Prev/next on a one-alert stack (F-080): the buttons exist and are
    //    clickable (no disabled state — EventDetailModal.tsx:1262-1277), and
    //    handleNavigate's bounds guard makes BOTH a no-op, so the score must
    //    HOLD. Arrow keys run the same handler (:413-427) and must hold too.
    //    This is the shipped behaviour pinned honestly; the two-alert case is
    //    the PR body's harness ask, not a claim made here.
    const score = page.getByTestId('risk-score');
    const smokeScoreText = String(h.smokeScenario.verdict.risk_score);
    await modal.getByRole('button', { name: 'Previous event' }).click();
    await expect(score, 'Previous is a bounds no-op on the only alert').toContainText(
      smokeScoreText
    );
    await modal.getByRole('button', { name: 'Next event' }).click();
    await expect(score, 'Next is a bounds no-op on the only alert').toContainText(smokeScoreText);
    await page.keyboard.press('ArrowLeft');
    await expect(score, 'ArrowLeft agrees with the button').toContainText(smokeScoreText);
    await page.keyboard.press('ArrowRight');
    await expect(score, 'ArrowRight agrees with the button').toContainText(smokeScoreText);

    // 6. Close through the modal's own button; grouped chrome intact (toggle
    //    back proves the page survived the navigation).
    await page.getByTestId('close-modal-button').click();
    await expect(modal, 'the close button closed the modal').toBeHidden({ timeout: 10_000 });
    await page.getByLabel('Group by camera').click();
    await expect(page.getByTestId('alerts-grouped-view')).toBeVisible();
    await expect(alertGroup).toBeVisible();

    // 7. End-to-end honesty: still the harness's UI; guard survived the drive.
    await assertGuardSurvives(page, h);
  });
});
