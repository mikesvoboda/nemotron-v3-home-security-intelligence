/**
 * F2.3 DO-2 golden path, the quiet-hours UI FORM — the leg notify.spec.ts
 * explicitly deferred ("the quiet-hours UI form drive (Add Period TOGGLES a
 * form, NotificationSettings.tsx:898/902 — its input round-trip is the next
 * file's job; this one pins the routes"). Routes stay there (F-232/F-233 API
 * legs); THIS file is their UI half: the toggle, the empty-label guard, the
 * Cancel-submits-nothing law, and one create-through-the-browser round trip
 * that ends by deleting its own row through the row's trash button.
 *
 * Laws this file encodes (all read at this head, cited by line):
 * - The button TOGGLES, it does not open: onClick is setShowQuietHoursForm(
 *   !showQuietHoursForm) (:898), so one button both shows and hides, and a
 *   second click after Cancel must also hide. There is no close X.
 * - Two stacked guards stop an empty label, and only the first is reachable
 *   from the UI: Save is disabled while !label.trim() || isPending (:981) and
 *   handleCreateQuietHours early-returns on !label.trim() (:332). A
 *   whitespace-only label proves .trim(), not mere emptiness. The handler
 *   guard is unreachable while the button is disabled — which is exactly why
 *   the cancel leg carries a REQUEST LISTENER instead of an assert: the
 *   contract is zero quiet-hours POSTs, and only the network layer can show
 *   an absence an assert cannot see. (Listener only — the guard from ../guard
 *   forbids route interception, and addCookies-style real state is fine.)
 * - The UI APPENDS SECONDS: inputs are type=time HH:MM and the handler sends
 *   `${start_time}:00` (:336-337), so a 23:15 entry stores 23:15:00 — the
 *   echo assert pins the contract the API-only file could not see.
 * - Form defaults are React state, not the API (:206-211): label '', times
 *   22:00/06:00, days Mon-Fri; the day buttons are 7 bare <button>s keyed by
 *   label (Mon…Sun, DAYS_OF_WEEK :90-98), selected state visible ONLY as the
 *   bg-purple-500 / bg-gray-700 class swap (:960-961) — toHaveClass is the
 *   whole evidence surface for the day toggle, and the submitted day SET is
 *   proven later by the create echo, which is the contract.
 * - Save success closes the form and RESETS state (:342-349, onSuccess
 *   setNewQuietHours to the defaults) and invalidates the list query
 *   (useNotificationPreferences.ts:393-401), which is what makes the new row
 *   appear without a reload; the row's delete is an aria-label'd trash button
 *   (aria-label={`Delete ${period.label}`} :1025) whose 204 has NO body —
 *   services/api.ts:1246-1249 returns undefined before any response.json(),
 *   so the UI leg doubles as the 204-parse regression gate.
 *
 * Locator cardinality (this tick's census — every locator here was counted
 * from source on the mount it runs on, per the sectionTitle lesson in
 * harness.ts): the notifications TAB renders exactly this one component
 * (App.tsx:287-303 — /settings children, one panel at a time; the shell's
 * only chrome is two scroll-chevron buttons, SettingsPage.tsx:89/:124).
 * Page-unique on this mount, each counted 1x: 'Add Period', 'Cancel', the
 * placeholder 'e.g., Night Time', 'No quiet hours configured', Mon/Tue/Wed/
 * Thu/Fri/Sat/Sun day labels, Save (literal :987); the component holds
 * exactly ONE type=text input (:916) and exactly TWO type=time inputs — so
 * form presence/absence is provable by counting inputs, not by hunting a
 * testid. A unique label string ('DO-2 ui window') makes the row and its
 * 'Delete …' button page-unique without touching src/ (ruling 87).
 */
import { expect, test } from '../guard';
import {
  adminSession,
  apiPath,
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

const QUIET_URL = '/api/notification-preferences/quiet-hours';
/** Unique to this spec: the row text, its Delete button and the finally-
 *  cleanup all key off it, and no seeded fixture carries it. */
const UI_LABEL = 'DO-2 ui window';

/** ids of every quiet-hours row the stack currently has — the restore
 *  proof is set equality against this snapshot, so a seeded stack is fine
 *  and this spec's row can never be confused with one. */
async function quietIds(api: Awaited<ReturnType<typeof authedFetch>>): Promise<string[]> {
  const res = await api.getJson(QUIET_URL);
  expect(res.status, 'GET quiet-hours answers 200').toBe(200);
  const items = Array.isArray(res.body?.items)
    ? res.body.items
    : Array.isArray(res.body)
      ? res.body
      : [];
  return items.map((row: Record<string, unknown>) => String(row.id)).sort();
}

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

test.describe('DO-2 quiet-hours UI form drive (F-232/F-233 UI half)', () => {
  test('the toggle toggles, Cancel submits nothing, and an empty or blank label cannot fire', async ({
    page,
  }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await expect(sectionTitle(page, 'Notification Settings')).toBeVisible();

    // Network witness: every quiet-hours POST this page attempts, recorded.
    // apiPath() equality, NOT endsWith(): an absence witness is exactly the
    // place a never-matching predicate is invisible — a matcher that cannot
    // fire makes `posts` empty for the WRONG reason, and toEqual([]) then
    // passes on a page that POSTed twice. api.ts:4448 ships this route
    // slashless today, so endsWith() works by accident; equality is immune to
    // a future slash flip on either side.
    const posts: string[] = [];
    page.on('request', (req) => {
      if (req.method() === 'POST' && apiPath(req.url()) === QUIET_URL) posts.push(req.url());
    });

    const addPeriod = page.getByRole('button', { name: 'Add Period', exact: true });
    const formInput = page.getByPlaceholder('e.g., Night Time');
    const timeInputs = page.locator('input[type="time"]');

    // Closed by default: useState(false) (:205) — the form is not merely
    // hidden, it is not rendered ({showQuietHoursForm && …} :911), and the
    // component has NO other type=text input, so a zero count is exact.
    await expect(addPeriod).toBeVisible();
    await expect(formInput).toHaveCount(0);
    await expect(timeInputs).toHaveCount(0);

    // --- open ---
    await addPeriod.click();
    await expect(formInput).toBeVisible();
    await expect(timeInputs).toHaveCount(2); // the component's only two (:930, :941)
    // React defaults (:206-211), not server state: 22:00 / 06:00, DOM order
    // is Start then End.
    await expect(timeInputs.first()).toHaveValue('22:00');
    await expect(timeInputs.nth(1)).toHaveValue('06:00');

    // Day defaults Mon-Fri selected, Sat/Sun not — the class swap is the
    // ONLY rendered difference (:960-961), and the submit contract (the day
    // SET) is pinned by the create echo in the next test, not here.
    const day = (label: string) => page.getByRole('button', { name: label, exact: true });
    await expect(day('Mon')).toHaveClass(/bg-purple-500/);
    await expect(day('Sat')).toHaveClass(/bg-gray-700/);
    await day('Sat').click();
    await expect(day('Sat'), 'clicking Sat selects it (handleToggleDay :363-368)').toHaveClass(
      /bg-purple-500/
    );
    await day('Mon').click();
    await expect(day('Mon'), 'clicking a selected day deselects it').toHaveClass(/bg-gray-700/);

    // --- empty-label guard, both shapes ---
    const save = page.getByRole('button', { name: 'Save', exact: true });
    await expect(save, 'Save is disabled while the label is empty (:981)').toBeDisabled();
    await formInput.fill('   '); // whitespace-only: proves .trim(), not emptiness
    await expect(save, 'a blank label is still no label').toBeDisabled();

    // --- Cancel submits nothing ---
    await formInput.fill(UI_LABEL); // a FULL label: the guard must be Cancel,
    await expect(save).toBeEnabled(); // not the disabled button, doing the work
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(formInput, 'Cancel unmounts the form (:973 setState false)').toHaveCount(0);
    expect(posts, 'Cancel POSTed nothing — the guard is client-side and total').toEqual([]);

    // --- the button itself is a TOGGLE, not an opener (:898) ---
    await addPeriod.click();
    await expect(formInput).toBeVisible();
    await addPeriod.click();
    await expect(formInput, 'a second Add Period click hides the form').toHaveCount(0);
    expect(posts, 'the whole toggle dance touched the API zero times').toEqual([]);
  });

  test('one save through the browser creates the row, shows it, and its trash button deletes it (restored)', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const before = await quietIds(api); // API leg FIRST: a blank UI can never
    let createdId = ''; // pass as "created" and no leak is left behind.
    try {
      await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
      await expect(sectionTitle(page, 'Notification Settings')).toBeVisible();
      await page.getByRole('button', { name: 'Add Period', exact: true }).click();

      await page.getByPlaceholder('e.g., Night Time').fill(UI_LABEL);
      // Non-default times so the echo cannot pass on a forgotten default.
      await page.locator('input[type="time"]').first().fill('23:15');
      await page.locator('input[type="time"]').nth(1).fill('06:45');
      await page.getByRole('button', { name: 'Sat', exact: true }).click(); // + Saturday
      await page.getByRole('button', { name: 'Mon', exact: true }).click(); // - Monday
      const sentDays = ['tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];

      const posted = page
        .waitForResponse((r) => apiPath(r.url()) === QUIET_URL && r.request().method() === 'POST')
        .then(async (r) => ({ status: r.status(), body: await r.json().catch(() => null) }));
      await page.getByRole('button', { name: 'Save', exact: true }).click();
      const res = await posted;
      createdId = String(res.body?.id ?? '');

      expect(res.status, 'Save POSTs and the route creates (201, as the API file pins)').toBe(201);
      expect(res.body?.label, 'echo carries the label typed in the browser').toBe(UI_LABEL);
      // THE UI-ONLY LAW (NotificationSettings.tsx:336-337): type=time values
      // are HH:MM and the handler appends ':00' before sending.
      expect(res.body?.start_time, 'HH:MM typed, HH:MM:00 sent').toBe('23:15:00');
      expect(res.body?.end_time, 'end likewise').toBe('06:45:00');
      expect([...(res.body?.days ?? [])].sort(), 'the toggled day set arrives').toEqual(
        [...sentDays].sort()
      );
      expect(createdId.length > 0, 'the response carries the new uuid').toBeTruthy();

      // onSuccess (:342-349) closes the form AND resets its state; the query
      // invalidation (:393-401 hooks) is what paints the row without reload.
      await expect(page.getByPlaceholder('e.g., Night Time')).toHaveCount(0);
      // Row-scoped, NOT page-wide: unlike every other locator in this file,
      // '23:15 - 06:45' is a DATA string — chrome censuses prove chrome
      // unique, they cannot see seed rows, and a seeded period with the same
      // window would strict-mode this assert (the r37 §4 latent-behind-first
      // class). The row div JSX is <div><Text>{label}</Text><Text>{window}
      // </Text></div> (:1008-1011), so the label's parent holds EXACTLY this
      // row's window line; the label itself is unique by construction.
      const myRow = page.getByText(UI_LABEL, { exact: true }).locator('xpath=ancestor::div[1]');
      await expect(myRow).toBeVisible();
      await expect(
        myRow.getByText('23:15 - 06:45'),
        'the row renders the stored times HH:MM (:1011 slice(0,5))'
      ).toBeVisible();

      const listed = await quietIds(api);
      expect(listed, 'the store sees the browser-created row').toContain(createdId);

      // Delete through the ROW, not the API: the trash button's accessible
      // name is the shipped template (`Delete ${label}` :1025). Exact-path
      // equality on the id — the client encodes the id through
      // encodeURIComponent (api.ts:4461), a no-op for a uuid's unreserved
      // chars, so the normalized path and this literal agree.
      const deleted = page
        .waitForResponse(
          (r) =>
            apiPath(r.url()) === `${QUIET_URL}/${createdId}` && r.request().method() === 'DELETE'
        )
        .then((r) => r.status());
      await page.getByRole('button', { name: `Delete ${UI_LABEL}`, exact: true }).click();
      // 204 carries NO body: services/api.ts:1246-1249 must return before
      // response.json() — a naive parse here surfaces as this leg failing.
      expect(await deleted, 'the row delete DELETEs 204').toBe(204);
      await expect(
        page.getByText(UI_LABEL, { exact: true }),
        'invalidateQueries drops the row without reload'
      ).toHaveCount(0);
    } finally {
      if (createdId) {
        await api.send(`${QUIET_URL}/${createdId}`, 'DELETE').catch(() => undefined);
      }
    }

    // Restore proof against the PRE-test snapshot — seeded rows included, so
    // "restored" means set equality, not emptiness.
    expect(await quietIds(api), 'the stack is exactly as this spec found it').toEqual(before);
  });

  test('the guard survives the quiet-hours form drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/settings/notifications`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Add Period', exact: true }).click();
    await expect(page.getByPlaceholder('e.g., Night Time')).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});
