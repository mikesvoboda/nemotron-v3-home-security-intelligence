/**
 * F2.3 DO-2 golden path, the browser-permission half of the notification
 * settings row (inventory F-234; claim #6996). The row's own contract is
 * CLIENT-ONLY ("— / browser Notification / service-worker / Web Audio APIs
 * only"), so there is no API leg and nothing to restore: no server state is
 * touched, and every browser fact here is per-context.
 *
 * Laws this file encodes (all read at this head, cited by line):
 * - ONE permission singleton, two sections: both hooks seed from the same
 *   mount-time read of Notification.permission (useDesktopNotifications
 *   .ts:210-214 and usePushNotifications.ts:115-120). context
 *   .grantPermissions(['notifications']) therefore flips BOTH badges — the
 *   inventory's claim that "push" here is the same browser permission, never
 *   a server subscription, is pinned by asserting both subtitles go green on
 *   one grant.
 * - The runner's un-granted default is the runner's business: headless
 *   Chromium ships 'denied' while a headed/flagged profile may sit at
 *   'default'. So the state leg does NOT hardcode a default — it reads
 *   Notification.permission at runtime and asserts the UI mirrors THAT value
 *   (badge text, subtitle branch, Enable-button presence are all pure
 *   functions of the same string; NotificationSettings.tsx:629-661). A pass
 *   here is the view-faithfulness contract in whichever world CI runs.
 * - Badge/percent text is NOT globally unique on this page: 'Enabled' also
 *   prints in the SMTP/webhook config rows (:1044/:1078) and every camera
 *   threshold badge prints "{threshold}%" (:868) — a bare "50%" or "Enabled"
 *   locator can bind the wrong row. All state pins therefore scope to their
 *   row container (ancestor::div[3] from the exact section label; DOM order
 *   and nesting read at this head) or use page-unique subtitle strings.
 * - Two volume controls, two storages (the trap this file refuses): the
 *   slider here is useIntegratedNotifications' AUDIO state (useAudio
 *   Notifications.ts:137 useState, seeded 0.5 via useIntegratedNotifications
 *   .ts:183's default — the page calls the hook with no options, :394), and
 *   it persists NOTHING. The ambient page's volume is a different control
 *   that writes the v1 localStorage key through useSettings.ts:282-296. So
 *   the round-trip asserted here is badge-follows-slider inside one mount;
 *   no storage read belongs in this file.
 * - The audio success banner proves the handler ran, not that a sound
 *   played: handleTestAudio sets the result OUTSIDE its `typeof AudioContext`
 *   guard (NotificationSettings.tsx:445-467), so on a context without Web
 *   Audio the message still prints. That is the shipped contract; asserting
 *   more than "the click round-trips to a success banner" would pin an
 *   accident of the browser image.
 * - Enable and Test buttons are the same ternary's two halves: Enable shows
 *   only while supported && !granted && !denied (:654), Test only when
 *   granted (:663). Their presence/absence is part of the state contract,
 *   not decoration.
 */
import { expect, test } from '../guard';
import { adminSession, assertGuardSurvives, grantNotifications, login, readHarness, type Harness } from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  await login(page, h, await adminSession(h));
}

/** The row container of a permission/audio section: the exact section label
 *  sits three divs below the justify-between row that also holds its badge
 *  (nesting read at NotificationSettings.tsx:624-675/:730-756). */
function rowOf(page: import('@playwright/test').Page, label: string) {
  return page
    .getByText(label, { exact: true })
    .locator('xpath=ancestor::div[3]');
}

test.describe('DO-2 browser permissions golden path (F-234)', () => {
  test('the UI mirrors Notification.permission whatever the runner starts at', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Notification Settings' })).toBeVisible();

    // Runtime read, not a remembered default: the UI's ternaries all key off
    // this same value, so the assertion below is the view-faithfulness proof
    // in either runner world (headless default 'denied' or 'default').
    const permission = await page.evaluate(() => Notification.permission);
    const desktopRow = rowOf(page, 'Desktop Notifications');
    const pushRow = rowOf(page, 'Push Notifications');

    if (permission === 'granted') {
      await expect(desktopRow.getByText('Enabled', { exact: true })).toBeVisible();
      await expect(page.getByText('Permission granted - notifications enabled')).toBeVisible();
    } else if (permission === 'denied') {
      await expect(desktopRow.getByText('Denied', { exact: true })).toBeVisible();
      await expect(page.getByText('Permission denied - enable in browser settings')).toBeVisible();
    } else {
      await expect(desktopRow.getByText('Not Set', { exact: true })).toBeVisible();
      await expect(page.getByText('Permission required for desktop alerts')).toBeVisible();
    }

    // The singleton law, un-granted side: push shows the SAME state string
    // because it reads the same Notification.permission (both hooks :210/:115).
    await expect(pushRow.getByText(permission === 'granted' ? 'Enabled' : permission === 'denied' ? 'Denied' : 'Not Set', { exact: true })).toBeVisible();
    if (permission !== 'granted') {
      await expect(page.getByText('Permission granted - push enabled')).toHaveCount(0);
    }

    // Button ternary: Enable exists ONLY in the never-asked state (:654),
    // and Test only once granted (:663) — both checked against the runtime
    // value so no runner default is assumed.
    const enableCount = permission === 'default' ? 2 : 0; // desktop + push rows
    await expect(page.getByRole('button', { name: 'Enable', exact: true })).toHaveCount(enableCount);
    await expect(page.getByRole('button', { name: 'Test', exact: true })).toHaveCount(
      permission === 'granted' ? 1 : 0
    );
  });

  test('a granted context: both sections go green on the one singleton, and both test handlers round-trip', async ({
    page,
    context,
  }) => {
    const h = harness as Harness;
    await grantNotifications(context); // context-wide, before any mount reads permission
    await signIn(page, h);
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Notification Settings' })).toBeVisible();

    const desktopRow = rowOf(page, 'Desktop Notifications');
    const pushRow = rowOf(page, 'Push Notifications');
    await expect(desktopRow.getByText('Enabled', { exact: true })).toBeVisible();
    await expect(pushRow.getByText('Enabled', { exact: true })).toBeVisible();
    await expect(page.getByText('Permission granted - notifications enabled')).toBeVisible();
    await expect(page.getByText('Permission granted - push enabled')).toBeVisible();
    // Ternary halves: the ask UI is gone, the send UI arrived.
    await expect(page.getByRole('button', { name: 'Enable', exact: true })).toHaveCount(0);

    // --- test desktop notification (the row's "sends a test desktop
    // notification" action): success banner, verbatim, from handleTestDesktop
    // (NotificationSettings.tsx:415-421). The 5 s auto-clear (:423) is the
    // clock this assert beats. ---
    await page.getByRole('button', { name: 'Test', exact: true }).click();
    await expect(page.getByText('Test desktop notification sent successfully!')).toBeVisible();

    // --- volume: badge follows the slider inside this mount (in-memory
    // contract; header explains why NO storage assert belongs here). Row
    // scoping dodges the camera "{threshold}%" badges. ---
    const volumeRow = rowOf(page, 'Volume Level');
    const slider = volumeRow.locator('input[type="range"]');
    await expect(slider).toHaveValue('0.5'); // useIntegratedNotifications.ts:183 default
    await expect(volumeRow.getByText('50%', { exact: true })).toBeVisible();
    await slider.fill('0.7'); // step 0.1 (:741-744); React onChange parses float
    await expect(volumeRow.getByText('70%', { exact: true })).toBeVisible();
    await slider.fill('0.5'); // tidy: same-mount default for anything reading later
    await expect(volumeRow.getByText('50%', { exact: true })).toBeVisible();

    // --- test audio: click → handler → success banner (proof the Web Audio
    // path ran without throwing; banner semantics per header) ---
    await page.getByRole('button', { name: 'Play Test', exact: true }).click();
    await expect(page.getByText('Test audio notification played successfully!')).toBeVisible();

    // F-237 identity on the permission rows: the standalone route is the same
    // component, so the SAME granted context shows the same green subtitles
    // there — permission follows the context, not the URL.
    await page.goto(`${h.ui}/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Permission granted - notifications enabled')).toBeVisible();
  });

  test('the guard survives the permission drive', async ({ page, context }) => {
    const h = harness as Harness;
    await grantNotifications(context);
    await signIn(page, h);
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Audio Notification Settings')).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});
