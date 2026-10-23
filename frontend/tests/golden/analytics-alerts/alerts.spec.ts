/**
 * F4.1 golden: the Alerts page over the ALERT table (inventory F-078 + F-079;
 * claim #7367).
 *
 * F4.1 rebuilt this page: /alerts now lists alert ROWS (GET
 * /api/alert-service/alerts — the table B4.1's pipeline writes) instead of the
 * events feed, and the design's witness sentence is "the alert appears live,
 * then acknowledge, dismiss, snooze" (docs/uplevel/4n-alerting.md:321). Each
 * verb below is driven and its wire effect pinned, in that order — the order
 * is not decoration: legacy acknowledge refuses a non-open alert with 409
 * (backend/api/routes/alerts.py), so Acknowledge MUST run while the row is
 * still open, and dismiss after it needs no restore because legacy dismiss
 * blocks only already-dismissed rows.
 *
 * Where the alert comes from: the harness's own smoke event
 * (harness-smoke.jpg, risk 61 → high), dropped by feature_check.py's smoke()
 * before golden starts — stack state this spec may rely on and must not
 * re-create (re-dropping its bytes inside the watcher's 300 s sha256 window
 * would just dedupe). The pipeline's derivation, each link code-verified:
 *   - the default rule is always in the pipeline's rule list (policy.py
 *     default_rule_from_settings: threshold 60, risk_filters
 *     critical/high/medium, severity MEDIUM, dedup "{camera_id}:default",
 *     cooldown 300);
 *   - smoke scores 61 ≥ threshold 60 and 'high' ∈ risk_filters, so
 *     _check_verdict_and_severity matches, and _higher_severity(rule MEDIUM,
 *     event HIGH) yields the alert severity HIGH;
 *   - the verdict chain lands on 'local' (fake VLM verdict + score → the
 *     local branch of verdict.py's source chain);
 *   - the created row (pipeline.py): status OPEN, event_id = the smoke event,
 *     match_count 1, channels [], metadata {rule_name 'default',
 *     matched_conditions, recognised}.
 *
 * Cross-run safety: smoke() drops the smoke fixture and awaits its verdict
 * BEFORE golden starts, so the pipeline has already created this run's alert
 * row by the time the spec runs — the poll keys on THAT row, by its event_id
 * (the smoke camera's newest event, read from the store). Rows left OPEN by a
 * dead earlier run name that run's own smoke event, an identity this run can
 * never re-derive (the fold never rewrites event_id), so the pre-flight sweep
 * dismisses every OPEN smoke-camera row EXCEPT one naming this run's event —
 * clearing the fold risk without touching the row this run polls for. A
 * DISMISSED row is un-foldable, and the final cleanup PUT pins the end state
 * unconditionally.
 *
 * The medium drop's absence moves to the alert-table level:
 * car-in-driveway (45) fails the default rule's threshold gate — 45 < 60 —
 * so no alert row may name the drop's event_id. Its PRESENT control is the
 * tier read (the drop is in the store at its own tier), so the absence is the
 * policy working, not the pipeline losing the event.
 * analytics.spec.ts (same directory, sorted after this file) still reads the
 * drop's data — the drop must happen here, exactly as it did when the old
 * spec owned it.
 *
 * What was removed with the old page and is NOT re-pinned: severity summary,
 * #risk-filter, grouped camera view, event-card testids, and the modal
 * prev/next round-trip — all chrome of the events-feed page the rewrite
 * deleted. The refresh instrument moves to the page's own endpoint, exact
 * pathname /api/alert-service/alerts; the Sidebar's useOpenAlertCount ALSO
 * fires that pathname once on mount (limit=1), so the refresh leg baselines
 * only after the request stream goes quiet.
 */
import type { Page } from '@playwright/test';

import { expect, test } from '../guard';
import {
  adminSessionAlerts as adminSession,
  apiWrite,
  assertDropEventStored,
  assertDropStoredItsDetection,
  assertGuardSurvivesAlerts as assertGuardSurvives,
  authedFetchAlerts as authedFetch,
  awaitVerdictedEvents,
  dropDo1Fixture,
  expectedTier,
  loginAlerts as login,
  readHarnessAlerts as readHarness,
} from '../harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** Wire shape of a row from GET /api/alert-service/alerts (the fields the
 *  asserts below read; AlertServiceResponse in schemas/alert_service.py). */
interface AlertRow {
  id: string;
  event_id: number;
  severity: string;
  status: string;
  verdict_source: string | null;
  match_count: number | null;
  camera_id: string | null;
  channels: string[];
  metadata: Record<string, unknown> | null;
  created_at: string;
}

/** Counts requests this PAGE sends to the alerts list — the page's own
 *  endpoint, matched on the EXACT pathname so sibling routes never inflate
 *  it. Installed before the /alerts navigation; a delta is a refetch. */
function installAlertsCounter(page: import('@playwright/test').Page): () => number {
  let count = 0;
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/alert-service/alerts') count += 1;
  });
  return () => count;
}

/** Read the alert-service list with the admin session. */
async function listAlerts(
  api: ReturnType<typeof authedFetch>,
  query: string
): Promise<{ status: number; rows: AlertRow[]; total: number }> {
  const { status, body } = await api.getJson(`/api/alert-service/alerts?${query}`);
  const items = (body?.items ?? []) as AlertRow[];
  return { status, rows: items, total: Number(body?.pagination?.total ?? 0) };
}

/** THIS row, across every filter and every earlier run: rule name and camera
 *  name are NOT unique keys (earlier runs leave dismissed smoke-camera rows
 *  behind, and the 'all' filter renders them all) — but the snooze select's
 *  aria-label carries the alert id (`Snooze alert ${alert.id}`), which is.
 *  A row that lost its id-bearing select would also lose every action below,
 *  so keying on it is the honest identity, not a convenience. */
function alertRow(page: Page, alertId: string) {
  return page
    .locator('[data-testid="alert-row"]')
    .filter({ has: page.locator(`select[aria-label="Snooze alert ${alertId}"]`) });
}

test.describe('F4.1 golden: /alerts lists alert rows and the design verbs work (F-078, F-079) @critical', () => {
  // Budget, itemised: 165 s for awaitVerdictedEvents (the drop's verdict) +
  // 60 s worst case for the smoke-alert poll (its own deadline, inside the
  // same window) + ~60 s of UI drive + margin. Same shape as the old spec's
  // 240 s: a near-deadline drop plus a full drive must still fit.
  test.setTimeout(240_000);

  test('the smoke alert appears live on /alerts, then acknowledge, dismiss and snooze land on the wire', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    // Installed before ANY navigation so no /api/alert-service/alerts request
    // can slip past the listener — the refresh leg below reads a delta.
    const countAlertsRequests = installAlertsCounter(page);

    // 1. The drop, through O2.2's own helper (documented contract, as
    //    dashboard-drop.spec.ts does). analytics.spec.ts reads the drop's
    //    data afterwards — the claim travels with this file's header.
    dropDo1Fixture(h);

    // 2. Backend first: the store read on the page's own terms before any UI.
    const session = await adminSession(h);
    const api = authedFetch(h, session);

    // THIS run's smoke event, by identity: smoke() dropped it and awaited its
    // verdict BEFORE golden started, so the pipeline has almost certainly
    // already created the row the poll below wants. The list is newest-first,
    // so limit=1 on the smoke camera names that event — the identity every
    // sweep and poll below keys on.
    const smokeEventPage = await api.getJson(`/api/events?camera_id=${h.smokeCameraId}&limit=1`);
    expect(smokeEventPage.status, 'the smoke camera answers an events read').toBe(200);
    const smokeEventId = ((smokeEventPage.body?.items ?? []) as Record<string, unknown>[])[0]?.id;
    expect(smokeEventId, 'the smoke event exists — smoke() ran before golden').toBeDefined();

    // PRE-FLIGHT SWEEP (cross-run safety, this header's contract): a run that
    // died between its verbs leaves OPEN smoke-camera rows naming ITS OWN
    // (long-gone) smoke event. Left open, the next smoke event inside the
    // cooldown folds silently into such a row — so sweep them dismissed. The
    // sweep must NOT touch rows naming THIS run's smoke event: smoke() ran
    // before golden, the pipeline already created that row, and dismissing it
    // would starve the poll below (the event alerts once, not twice). Only
    // rows for THIS fixture's camera are touched; other cameras' alerts are
    // not ours.
    {
      const { rows: openRows } = await listAlerts(api, 'status=open&limit=100');
      const staleRows = openRows.filter(
        (r) => r.camera_id === h.smokeCameraId && String(r.event_id) !== String(smokeEventId)
      );
      for (const stale of staleRows) {
        await apiWrite(h, session, 'PUT', `/api/alert-service/alerts/${stale.id}`, {
          status: 'dismissed',
        });
      }
    }

    // The PRESENT control for the absence below: the drop is in the store,
    // tiered exactly where the book puts it, so the pipeline ran.
    const items = await awaitVerdictedEvents(h, api, 165_000);
    const dropEventId = assertDropEventStored(items, h);
    assertDropStoredItsDetection(items, h);
    const dropTier = expectedTier(h.scenario.verdict.risk_score);
    const tierPage = await api.getJson(`/api/events?risk_level=${dropTier}`);
    expect(tierPage.status, `the ${dropTier} page answers`).toBe(200);
    const tierIds = ((tierPage.body?.items ?? []) as Record<string, any>[]).map((e) =>
      String(e.id)
    );
    expect(tierIds, 'the drop is listed by its own tier — the pipeline ran').toContain(dropEventId);

    // 3. THE ALERT APPEARS LIVE. Poll the page's own endpoint for an OPEN row
    //    naming THIS run's smoke event (not just the camera: on a persistent
    //    stack an older run's OPEN row could still be for the same camera).
    //    The smoke event may still be inside the pipeline when the drive
    //    starts (smoke() drops ~40 s before golden, but "appears live" is the
    //    design's own claim, so the poll is part of the pin). The fold cannot
    //    resurrect a dismissed row, and the sweep above left this run's row —
    //    if there is one — standing.
    const smokePollDeadline = Date.now() + 60_000;
    let smokeAlert: AlertRow | undefined;
    let dropAlertCount = 0;
    while (Date.now() < smokePollDeadline) {
      const { rows } = await listAlerts(api, 'status=open&limit=100');
      dropAlertCount = rows.filter((r) => String(r.event_id) === String(dropEventId)).length;
      smokeAlert = rows.find(
        (r) => r.camera_id === h.smokeCameraId && String(r.event_id) === String(smokeEventId)
      );
      if (smokeAlert && dropAlertCount === 0) break;
      await new Promise((resolve) => setTimeout(resolve, 3_000));
    }
    expect(
      smokeAlert,
      "no open alert for this run's smoke event within 60 s: the pipeline did not alert " +
        "the smoke drop (threshold 60 / risk_filters), the sweep dismissed this run's own " +
        'row (the sweep spares rows naming the smoke event), or an older row folded this ' +
        'smoke event away inside the cooldown — see this file header, cross-run safety'
    ).toBeDefined();
    expect(
      dropAlertCount,
      'the medium drop produced NO alert row — 45 fails the default rule threshold ' +
        '(60) end to end (policy.py _check_verdict_and_severity)'
    ).toBe(0);

    // The row's full derived shape, each field tied to its source link.
    const alert = smokeAlert as AlertRow;
    expect(alert.severity, '_higher_severity(rule MEDIUM, event HIGH) → HIGH').toBe('high');
    expect(alert.status, 'a fresh pipeline row starts OPEN').toBe('open');
    expect(alert.verdict_source, 'the fake VLM verdict chain lands on local').toBe('local');
    expect(alert.match_count, 'a fresh row has folded nothing yet').toBe(1);
    expect(alert.channels, 'nothing has been told yet').toEqual([]);
    expect((alert.metadata ?? {}).rule_name, 'the default rule names itself in metadata').toBe(
      'default'
    );
    expect(String(alert.event_id), 'row sanity: not the drop').not.toBe(String(dropEventId));

    // The camera NAME the row renders (cameraNameMap over /api/cameras;
    // AlertsPage falls back to the raw id only while the cameras query is in
    // flight). Read, not guessed — the row's rendered Camera line is pinned
    // below as chrome.
    const camPage = await api.getJson('/api/cameras');
    const cameras = ((camPage.body?.items ?? []) as Record<string, any>[]).filter(
      (c) => String(c.id) === h.smokeCameraId
    );
    expect(cameras.length, 'the smoke camera is seeded').toBe(1);
    const cameraName = String(cameras[0].name ?? h.smokeCameraId);

    // 4. The page. Logged in, booting to /alerts — the open filter is the
    //    shipped default. The row is pinned by rule name AND camera name
    //    together: the store is global, and another camera could carry its
    //    own default-rule alert — a filter on 'default' alone would make the
    //    action buttons below ambiguous (strict mode would redden, but with a
    //    message pointing at the wrong cause).
    await login(page, h, session);
    await page.goto(`${h.ui}/alerts`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('alerts-page')).toBeVisible({ timeout: 30_000 });

    const row = alertRow(page, alert.id);
    await expect(row, 'the smoke alert appears live on the page').toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByText(/alert(s)? found/),
      'the count line renders from totalCount'
    ).toBeVisible();

    // The row's chrome, each piece the rewrite ships (AlertsPage.tsx):
    await expect(
      page.getByTestId(`alert-severity-${alert.severity}`),
      'the severity badge is the derived tier'
    ).toBeVisible();
    await expect(
      page.getByText('verified locally', { exact: true }),
      'the verdict badge reads the local chain'
    ).toBeVisible();
    await expect(
      page.getByText('nobody yet', { exact: true }),
      'with empty channels the row says who was NOT told'
    ).toBeVisible();
    await expect(
      row.getByText(`Camera: ${cameraName}`, { exact: false }),
      'the row resolves the camera id to its seeded name'
    ).toBeVisible();

    // 5. ACKNOWLEDGE — the design's first verb. The page calls the legacy
    //    route (alertsApi.ts acknowledgeAlert → POST /api/alerts/{id}/
    //    acknowledge), the same Alert table; the route admits OPEN and
    //    broadcasts ALERT_ACKNOWLEDGED, which invalidates alertsQueryKeys.all
    //    and repaints the row out of the open filter.
    await row.getByRole('button', { name: 'Acknowledge' }).click();
    const ackDeadline = Date.now() + 20_000;
    let acked = false;
    while (Date.now() < ackDeadline && !acked) {
      const { rows: openRows } = await listAlerts(api, 'status=open&limit=100');
      const { rows: ackRows } = await listAlerts(api, 'status=acknowledged&limit=100');
      acked = !openRows.some((r) => r.id === alert.id) && ackRows.some((r) => r.id === alert.id);
      if (!acked) await new Promise((resolve) => setTimeout(resolve, 2_000));
    }
    expect(acked, 'acknowledge moved the row open → acknowledged on the wire').toBe(true);
    await expect(row, 'the acknowledged row leaves the open list').toHaveCount(0, {
      timeout: 15_000,
    });

    // 6. DISMISS — from acknowledged, which legacy dismiss admits (it blocks
    //    only already-dismissed rows). Driven through the all filter where
    //    the row still renders.
    await page.locator('#status-filter').selectOption('all');
    const rowAll = alertRow(page, alert.id);
    await expect(rowAll, 'the all filter shows the acknowledged row').toBeVisible({
      timeout: 15_000,
    });
    await rowAll.getByRole('button', { name: 'Dismiss' }).click();
    const disDeadline = Date.now() + 20_000;
    let dismissed = false;
    while (Date.now() < disDeadline && !dismissed) {
      const { rows: disRows } = await listAlerts(api, 'status=dismissed&limit=100');
      dismissed = disRows.some((r) => r.id === alert.id);
      if (!dismissed) await new Promise((resolve) => setTimeout(resolve, 2_000));
    }
    expect(dismissed, 'dismiss moved the row to dismissed on the wire').toBe(true);

    // 7. SNOOZE — the design's third verb, riding the row's triggering event
    //    (AlertsPage handleSnooze → useSnoozeEvent → PATCH /api/events/{id}
    //    snooze_until; the backend syncs that write into an activity snooze).
    //    Restore the row to open so it renders on the open page again — the
    //    snooze rides the EVENT, not the alert status; the row is merely the
    //    shipped control surface.
    await apiWrite(h, session, 'PUT', `/api/alert-service/alerts/${alert.id}`, {
      status: 'open',
    });
    await page.locator('#status-filter').selectOption('open');
    await expect(row, 'the restored row is back on the open page').toBeVisible({
      timeout: 15_000,
    });
    await row.locator(`select[aria-label="Snooze alert ${alert.id}"]`).selectOption('900');
    // The wire fact: the event's snooze_until lands ~15 min ahead (the client
    // computes Date.now() + seconds; api.ts snoozeEvent). Poll the
    // single-event GET.
    const snoozeDeadline = Date.now() + 20_000;
    let snoozedUntil: string | null = null;
    while (Date.now() < snoozeDeadline && snoozedUntil === null) {
      const { body } = await api.getJson(`/api/events/${alert.event_id}`);
      const until = (body as Record<string, unknown> | null)?.snooze_until;
      snoozedUntil = typeof until === 'string' ? until : null;
      if (snoozedUntil === null) await new Promise((resolve) => setTimeout(resolve, 2_000));
    }
    expect(snoozedUntil, 'the snooze click stored snooze_until on the event').not.toBeNull();
    const deltaMinutes = (new Date(String(snoozedUntil)).getTime() - Date.now()) / 60_000;
    expect(
      deltaMinutes,
      `a 15-minute option stores ~15 min ahead (got ${deltaMinutes.toFixed(2)})`
    ).toBeGreaterThan(13);
    expect(deltaMinutes).toBeLessThan(17);

    // Clean the snooze residue NOW, not in an afterAll: PATCH null is what
    // the client's own unsnooze does (api.ts) and what deletes the synced
    // activity-snooze rows (_sync_event_activity_snooze). The event belongs
    // to the harness smoke camera — a run that died after this point would
    // otherwise leave the smoke event snoozed for the whole household.
    await apiWrite(h, session, 'PATCH', `/api/events/${alert.event_id}`, {
      snooze_until: null,
    });

    // 8. Cross-run cleanup, the header's contract: leave every alert row
    //    naming this run's smoke event DISMISSED (the restore above re-opened
    //    this one; PUT again unconditionally so the end state does not depend
    //    on timing). A dismissed row cannot fold the next run's smoke event.
    await apiWrite(h, session, 'PUT', `/api/alert-service/alerts/${alert.id}`, {
      status: 'dismissed',
    });
    const final = await listAlerts(api, `event_id=${alert.event_id}`);
    expect(
      final.rows.every((r) => r.status === 'dismissed'),
      "every alert row naming this run's smoke event ends dismissed — the fold " +
        "(OPEN-only) cannot swallow the next run's alert"
    ).toBe(true);

    // 9. Refresh (F-078's "refreshes" clause). handleRefresh is `void
    //    refetch()` — the click's observable is a REQUEST to the page's own
    //    endpoint, and it is attributable to the click: useAlertsQuery's
    //    refetchInterval defaults to false and the page passes none, so
    //    nothing on this page polls on a timer. The Sidebar's
    //    useOpenAlertCount DOES fire the same pathname once on mount
    //    (limit=1), so the baseline is taken only after the request stream
    //    goes quiet — three equal samples 500 ms apart, bounded at 15 s so a
    //    stream that never settles fails here instead of silently
    //    attributing someone else's request to the click.
    let alertsRequestsBefore = countAlertsRequests();
    let quietSamples = 0;
    for (let sample = 0; sample < 30 && quietSamples < 3; sample++) {
      await page.waitForTimeout(500);
      const now = countAlertsRequests();
      quietSamples = now === alertsRequestsBefore ? quietSamples + 1 : 0;
      alertsRequestsBefore = now;
    }
    expect(quietSamples, 'the alerts request stream went quiet for the baseline').toBe(3);
    await page.getByRole('button', { name: 'Refresh alerts' }).click();
    await expect
      .poll(() => countAlertsRequests(), { timeout: 10_000, intervals: [200, 400, 800] })
      .toBeGreaterThan(alertsRequestsBefore);

    // End-of-spec honesty: the guard survived the whole drive (F2.1's pin,
    // re-armed so a DO-1 spec that reached for a mock fails LOUD).
    await assertGuardSurvives(page, h);
  });
});
