/**
 * F2.3 DO-2 golden path, notifications half (inventory F-230 to F-237 minus
 * F-234's permission arms, which live in permission.spec.ts; claim #6996).
 *
 * DROPS NOTHING (harness.ts header: this batch is settings/permission/storage,
 * not events), and every mutation this file makes is restored in the same test
 * it belongs to — by the final-status leg (the flip-back PUT 200, the
 * camera-row PUT 200 carrying its prior threshold back, the quiet-hours DELETE
 * 204), with a swallowed belt-and-braces DELETE behind it for the case where
 * an assert threw first. That restore discipline is what makes a gate re-run
 * against the same stack start from the same state, and it does not depend on
 * position: this file sorts LAST in the golden project at the current head,
 * but the pending #6986/#6978 batches add operations/ and shell/ after
 * 'notify-access' (harness.ts header has the counts), so "last" is a fact
 * about today's tree and is deliberately not load-bearing here.
 *
 * What it proves per row (every backend fact read BEFORE the UI that renders
 * it, so a blank screen can never pass as "renders"):
 *  F-230  GET /api/notification-preferences is the shipped singleton default
 *         (id 1, enabled true, sound 'default', risk_filters exactly
 *         critical/high/medium — routes/notification_preferences.py:56-86
 *         creates exactly this on first read); the UI's toggle is the SAME
 *         state: switch aria-checked matches the API, one click PUTs the flip
 *         (NotificationSettings.tsx:282-284 sends { enabled: !preferences
 *         .enabled } alone), the API shows it, a second click restores it.
 *         Sound Select exists showing the stored value — the change leg is
 *         NOT here (Tremor open-before-pin needs its own CI-proven round
 *         trip; inventory 'picks a sound' stays half-pinned by read-side).
 *  F-231  per-camera thresholds, API legs only: PUT 70 echoes 70 (schemas
 *         :90-94,102), PUT 101 → 422 (ge=0 le=100 rejected before the
 *         handler), PUT an unknown camera id → 404 with the handler's own
 *         detail shape (:253-258). The row is RESTORED to what the GET list
 *         said before the flip — the 60 default (DEFAULT_CAMERA_RISK_
 *         THRESHOLD) is deliberately NOT asserted: it only appears when no
 *         setting row exists, and the fake stack's seed order is not this
 *         spec's to depend on.
 *  F-232  quiet-hours create: POST 201 echoes label/times/days
 *         (QuietHoursPeriodCreate schema, :159-179); the list sees it; the
 *         ONE documented validation edge — start_time == end_time → 400
 *         (:347/:355) — is a real branch, not a guessed string.
 *  F-233  delete: DELETE → 204, the list drops it, and a second DELETE of
 *         the now-unknown id → 404 (:401/:407) — one leg proves both.
 *  F-235  GET /api/notification/config in the no-env CI stack (neither
 *         docker-compose.ci.yml nor docker-compose.fake-ai.yml carries any
 *         SMTP/webhook env — grepped at implementation): the three
 *         configured flags are false and available_channels is []
 *         (services/notification.py:141-166: email needs host AND from
 *         address, webhook needs default_webhook_url, push is a literal
 *         False). The UI renders that state, not a spinner: the two
 *         not-configured guidance strings (:1113-1119, :1174-1178) and the
 *         empty channels summary (:1193) are visible.
 *  F-236  the shipped STUB contract, demoted honestly (the inventory's
 *         'expects a log' action can never pass — routes/notification.py:412
 *         returns a literal empty list): GET /api/notification/history → 200
 *         with entries [] and count 0, and the panel mounts its no-filter
 *         empty copy VERBATIM (NotificationHistoryPanel.tsx:277-290).
 *  F-237  standalone /notifications and the /settings/notifications tab
 *         mount the SAME component: the same heading, the same Global
 *         Preferences block, the same channels guidance — and the standalone
 *         page additionally owns its 'Back to Settings' link
 *         (NotificationPreferencesPage.tsx:43) which the tab does not.
 *
 * Deliberate non-legs: F-234's permission arms (context.grantPermissions
 * belongs to its own spec so its badge asserts sit next to the grant they
 * depend on); the Test Email/Webhook buttons (they do not render in this
 * stack at all — the guidance REPLACES them, :1113-1119); the quiet-hours UI
 * form drive (Add Period TOGGLES a form, NotificationSettings.tsx:898/902 —
 * its input round-trip is quiet-hours.spec.ts's job, written after this
 * file; this one pins the routes).
 */
import { expect, test } from '../guard';
import {
  adminSession,
  assertGuardSurvives,
  authedFetch,
  login,
  readHarness,
  sectionTitle,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** The shipped first-read default (routes/notification_preferences.py:66-83
 *  creates exactly this when no row exists). A golden stack is fresh per
 *  feature-check run, and this file restores anything it changes — so a
 *  failure here means either the shipped default changed (a real contract
 *  move: update this expectation with the route) or a mutation leaked without
 *  restore (a bug in THIS file — check the finally blocks first). */
const DEFAULT_ENABLED = true;
const DEFAULT_SOUND = 'default';
const DEFAULT_RISK_FILTERS = ['critical', 'high', 'medium'];

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

test.describe('DO-2 notifications golden path', () => {
  test('F-230/F-237 global preferences: API default drives the UI, and both mounts agree', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // --- API leg: the singleton's shipped default, read before any UI ---
    const first = await api.getJson('/api/notification-preferences');
    expect(first.status, 'GET notification-preferences answers 200').toBe(200);
    expect(first.body?.id, 'the preferences row is the singleton id 1').toBe(1);
    expect(
      first.body?.enabled,
      'shipped default enabled — see DEFAULT_ENABLED comment for the two failure readings'
    ).toBe(DEFAULT_ENABLED);
    expect(first.body?.sound, 'shipped default sound').toBe(DEFAULT_SOUND);
    expect([...(first.body?.risk_filters ?? [])].sort(), 'shipped default risk filters').toEqual(
      [...DEFAULT_RISK_FILTERS].sort()
    );

    // --- UI leg on the SETTINGS tab mount ---
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    // sectionTitle, NOT getByRole('heading'): Tremor's <Title> renders a <p>
    // and the tab shell owns the page's only <h1> ("Settings") — harness.ts
    // documents the CI failure that proved it.
    await expect(sectionTitle(page, 'Notification Settings')).toBeVisible();
    await expect(page.getByText('Global Preferences')).toBeVisible();
    const toggle = page.getByRole('switch', { name: 'Toggle notifications' });
    await expect(toggle).toBeVisible();
    // aria-checked mirrors the API fact (NotificationSettings.tsx:546).
    await expect(toggle).toHaveAttribute('aria-checked', String(DEFAULT_ENABLED));

    // --- one click PUTs exactly { enabled: flip }; API confirms; UI follows ---
    let flipped = false;
    try {
      const put = page
        .waitForResponse(
          (r) => r.url().endsWith('/api/notification-preferences') && r.request().method() === 'PUT'
        )
        .then(async (r) => ({ status: r.status(), body: await r.json().catch(() => null) }));
      await toggle.click();
      const res = await put;
      flipped = true;
      expect(res.status, 'the toggle PUT succeeds').toBe(200);
      expect(res.body?.enabled, 'the PUT response carries the flip').toBe(!DEFAULT_ENABLED);
      await expect(toggle, 'the switch paints the new state').toHaveAttribute(
        'aria-checked',
        String(!DEFAULT_ENABLED)
      );
      const after = await api.getJson('/api/notification-preferences');
      expect(
        after.body?.enabled,
        'the store carries the flip — the UI is a view, not a paint'
      ).toBe(!DEFAULT_ENABLED);
    } finally {
      if (flipped) {
        const restore = page
          .waitForResponse(
            (r) =>
              r.url().endsWith('/api/notification-preferences') && r.request().method() === 'PUT'
          )
          .then((r) => r.status());
        await toggle.click();
        expect(await restore, 'restoring the default PUTs 200').toBe(200);
      }
    }
    const restored = await api.getJson('/api/notification-preferences');
    expect(restored.body?.enabled, 'preferences restored for the next spec').toBe(DEFAULT_ENABLED);

    // --- F-237: the standalone route is the SAME component + its own back link ---
    await page.goto(`${h.ui}/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(
      sectionTitle(page, 'Notification Settings'),
      '/notifications mounts the same NotificationSettings section title'
    ).toBeVisible();
    await expect(page.getByText('Global Preferences')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to Settings' })).toBeVisible();
    // The tab mount has NO back link of its own (it lives inside /settings);
    // that asymmetry is what makes this an equality-with-identity proof.
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(
      page.getByRole('link', { name: 'Back to Settings' }),
      'the tab mount does not carry the standalone page chrome'
    ).toHaveCount(0);
  });

  test('F-235 channels: the no-env stack is not-configured end to end', async ({ page }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // --- API leg: every configured predicate is false by compose, not guess ---
    const cfg = await api.getJson('/api/notification/config');
    expect(cfg.status, 'GET notification/config answers 200').toBe(200);
    expect(cfg.body?.email_configured, 'no SMTP env in the CI stack').toBe(false);
    expect(cfg.body?.webhook_configured, 'no webhook env in the CI stack').toBe(false);
    expect(cfg.body?.push_configured, 'push_configured is a shipped constant false').toBe(false);
    expect(cfg.body?.available_channels, 'no channel passes its predicate').toEqual([]);

    // --- UI leg: the guidance REPLACES the test buttons (that is the pin) ---
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Email notifications are not configured.')).toBeVisible();
    await expect(page.getByText('Webhook notifications are not configured.')).toBeVisible();
    await expect(page.getByText('No notification channels configured')).toBeVisible();
    // NO button-absence assert: the DESKTOP Test button (:668) renders in
    // this stack regardless of channel config (it is browser-side), so a
    // global "no Test buttons" count fails against a healthy app. The email/
    // webhook sections showing guidance INSTEAD of their buttons is already
    // pinned by the guidance strings above plus the flags=false API leg.
  });

  test('F-236 history: the stub contract is 200-empty and the panel says so verbatim', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const hist = await api.getJson('/api/notification/history');
    expect(hist.status, 'GET notification/history answers 200 (the shipped stub)').toBe(200);
    expect(hist.body?.entries, 'the stub returns a literal empty list (:412)').toEqual([]);
    expect(hist.body?.count, 'and count 0').toBe(0);

    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('No notification history yet')).toBeVisible();
    await expect(page.getByText('Notification delivery records will appear here')).toBeVisible();
    // The filtered twin must NOT be on the page — its absence proves the
    // panel took the no-filter branch, not a catch-all render.
    await expect(page.getByText('No notification history matches your filters')).toHaveCount(0);
  });

  test('F-231/F-232/F-233 the mutation routes: camera thresholds and quiet-hours CRUD (restore everything)', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // ---- F-231 per-camera threshold, against a camera the stack really has ----
    const cameras = await api.getJson('/api/cameras');
    expect(cameras.status, 'GET /api/cameras answers 200').toBe(200);
    const list = Array.isArray(cameras.body?.items) ? cameras.body.items : cameras.body;
    expect(Array.isArray(list) && list.length > 0, 'the fake stack seeded cameras').toBeTruthy();
    const cameraId = String((list as Record<string, unknown>[])[0].id);

    const before = await api.getJson('/api/notification-preferences/cameras');
    expect(before.status, 'GET camera notification settings answers 200').toBe(200);
    const rows: Record<string, any>[] = Array.isArray(before.body?.items)
      ? before.body.items
      : Array.isArray(before.body)
        ? before.body
        : [];
    const prior = rows.find((row) => String(row.camera_id) === cameraId);
    // Restore target: the stored value, or the route's create-default — read
    // from the API itself rather than importing the constant, so the 50-from-
    // the-schema-example trap and the 60-from-models trap are both avoided.
    const restoreThreshold = prior ? Number(prior.risk_threshold) : null;
    const restoreEnabled = prior ? Boolean(prior.enabled) : null;

    const set70 = await api.send(`/api/notification-preferences/cameras/${cameraId}`, 'PUT', {
      risk_threshold: 70,
    });
    expect(set70.status, 'PUT risk_threshold=70 is accepted').toBe(200);
    expect(Number(set70.body?.risk_threshold), 'the response echoes 70').toBe(70);
    try {
      const tooHigh = await api.send(`/api/notification-preferences/cameras/${cameraId}`, 'PUT', {
        risk_threshold: 101,
      });
      expect(tooHigh.status, '101 breaches the schema bound le=100 before the handler').toBe(422);

      const ghost = await api.send(
        '/api/notification-preferences/cameras/no-such-camera-do2',
        'PUT',
        { risk_threshold: 70 }
      );
      expect(ghost.status, 'an unknown camera id 404s (:253-258)').toBe(404);
      expect(String(ghost.body?.detail), 'the 404 names the camera').toContain('not found');
    } finally {
      if (prior) {
        const back = await api.send(`/api/notification-preferences/cameras/${cameraId}`, 'PUT', {
          enabled: restoreEnabled,
          risk_threshold: restoreThreshold,
        });
        expect(back.status, 'the camera row is restored for the next run').toBe(200);
        expect(Number(back.body?.risk_threshold), 'restore carries the prior threshold back').toBe(
          restoreThreshold
        );
      }
      // No-prior-row case: the PUT created the row and the routes offer NO
      // DELETE for camera settings (GET :165/:188, PUT :225 — read at this
      // head), so removal is not available and no PUT of an empty body is
      // pretended to be one. The residue is deterministic: run 2+ reads the
      // row as prior=70 and the branch above restores 70, so the stack is
      // idempotent from the second gate run onward. Documented, not hidden.
    }

    // ---- F-232/F-233 quiet-hours CRUD with guaranteed delete ----
    const created = await api.send('/api/notification-preferences/quiet-hours', 'POST', {
      label: 'DO-2 golden window',
      start_time: '22:00:00',
      end_time: '06:00:00',
      days: ['monday'],
    });
    expect(created.status, 'POST quiet-hours creates (201)').toBe(201);
    const periodId = String(created.body?.id ?? '');
    expect(periodId.length > 0, 'the response carries the new uuid').toBeTruthy();
    expect(created.body?.label, 'create echoes the label').toBe('DO-2 golden window');
    expect(created.body?.start_time, 'create echoes start').toBe('22:00:00');
    expect(created.body?.days, 'create echoes the day set').toEqual(['monday']);

    try {
      const listAfter = await api.getJson('/api/notification-preferences/quiet-hours');
      expect(listAfter.status, 'GET quiet-hours answers 200').toBe(200);
      const items = Array.isArray(listAfter.body?.items) ? listAfter.body.items : [];
      expect(
        items.some((row: Record<string, any>) => String(row.id) === periodId),
        'the list sees the created period'
      ).toBeTruthy();

      const zeroLength = await api.send('/api/notification-preferences/quiet-hours', 'POST', {
        label: 'DO-2 zero length',
        start_time: '08:00:00',
        end_time: '08:00:00',
        days: ['monday'],
      });
      expect(zeroLength.status, 'start == end is the ONE documented 400 (:347/:355)').toBe(400);

      const deleted = await api.send(
        `/api/notification-preferences/quiet-hours/${periodId}`,
        'DELETE'
      );
      expect(deleted.status, 'DELETE answers 204').toBe(204);
      const listGone = await api.getJson('/api/notification-preferences/quiet-hours');
      const stillThere = (Array.isArray(listGone.body?.items) ? listGone.body.items : []).some(
        (row: Record<string, any>) => String(row.id) === periodId
      );
      expect(stillThere, 'the list drops the deleted period').toBeFalsy();

      const again = await api.send(
        `/api/notification-preferences/quiet-hours/${periodId}`,
        'DELETE'
      );
      expect(again.status, 'the now-unknown id 404s (:401/:407)').toBe(404);
    } finally {
      // belt and braces: if an assert above threw before the DELETE landed,
      // do not leave a DO-2 period in the stack.
      await api
        .send(`/api/notification-preferences/quiet-hours/${periodId}`, 'DELETE')
        .catch(() => undefined);
    }
  });

  test('the guard survives the whole notifications drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Global Preferences')).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});
