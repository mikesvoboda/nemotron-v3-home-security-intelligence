/**
 * F2.3 DO-4 golden path — F-248, delete a webhook and confirm.
 *
 * Inventory row (F-248): "clicks Delete on a webhook and confirms", over
 * `DELETE /api/outbound-webhooks/{webhook_id}`.
 *
 * THE DIALOG IS NATIVE, AND THAT IS A FIRST IN THIS TREE.
 * WebhooksPage.tsx:200 confirms with `window.confirm(...)`, not an in-app modal.
 * Measured at this head: `grep -rn "on('dialog'|waitForEvent('dialog'|
 * runAndWaitForDialog" frontend/tests/golden/` → 0, and the same search over
 * frontend/tests/e2e/ → 0 — the e2e tree's `confirmDelete()` page-object methods
 * (AlertRulesPage.ts:441, ZonesPage.ts:351) click an in-APP modal button, so there is
 * no precedent to copy here and no prior art to trust. What this file uses is
 * `page.waitForEvent('dialog')`: Playwright's own event for the browser dialog the page
 * raises, awaited rather than handled fire-and-forget (see ARM 1 for why — the read of
 * the captured message must not be able to win a race against the handler). That is the
 * golden contract intact — the F2.1 guard blocks ROUTE
 * INTERCEPTION (route/unroute/routeFromHAR/routeWebSocket, guard.ts:46) and
 * `assertGuardSurvives` is re-armed at the end of this file to prove it still bites;
 * the dialog event does not intercept or fabricate traffic, it answers the page's own
 * native prompt so the page's own code can run. (The alternative — addInitScript to
 * replace window.confirm — is the in-tree state-seeding mechanism (guard.ts seeds tour
 * keys; operations/databases.spec.ts:44 seeds a localStorage flag), but replacing the
 * function the row under test depends on would be faking the very thing F-248 is about,
 * which is that the user says "yes" to the browser.)
 *
 * What each arm proves, and where the row's Delete button actually lives:
 * - THERE IS NO ALWAYS-VISIBLE DELETE. It exists only inside the row's `More actions`
 *   dropdown (WebhookList.tsx:214-221), whose menu is a plain <div> — NOT role="menu" —
 *   so the item is reached as a bare `button` named `Delete`. `Edit` also appears twice
 *   on the page, and `More actions` is per-row, so every locator here is scoped to
 *   `webhook-row-<id>`: the dropdown renders inside the row's own <td>, which is what
 *   makes row scope sufficient.
 * - DISMISS MUST FIRE NOTHING. handleDelete early-returns on a false confirm
 *   (WebhooksPage.tsx:201), so the DELETE leg is an ABSENCE — and an absence needs a
 *   positive anchor next to it or a matcher that cannot match passes vacuously
 *   (notify-access/harness.ts:240-251). The anchors are: the dialog message asserted
 *   with the row's own name, the row still in the DOM, and the row still in the STORE
 *   (an API read — a UI still showing a row proves only the UI).
 * - ACCEPT DELETES, AND THE DISAPPEARANCE IS A REFETCH. onSuccess invalidates
 *   ['webhooks','list'] and ['webhooks','health'] and removeQueries the detail
 *   (useWebhooks.ts:639-652); there is no optimistic path (0 hits for onMutate/
 *   setQueryData in that file). So the spec witnesses the list AND health GETs that
 *   follow the 204, and only then asserts absence.
 *
 * Locator cardinality counted on this mount: 'More actions' is 1× per row and `Delete`
 * is one of four bare dropdown buttons; page-wide 'Delete' occurs 14× across the mounted
 * files (mostly JSDoc), which is exactly why nothing here uses a page-wide Delete.
 */
import { expect, test } from '../guard';
import {
  adminSession,
  apiPath,
  assertGuardSurvives,
  authedFetch,
  createWebhook,
  deleteWebhook,
  login,
  readHarness,
  webhookIds,
  WEBHOOKS_URL,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

const ROW_NAME = 'DO-4 f248 delete row';

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

function watchRequests(page: Parameters<typeof login>[0]): string[] {
  const log: string[] = [];
  page.on('request', (req) => log.push(`${req.method()} ${apiPath(req.url())}`));
  return log;
}

const countOf = (log: string[], entry: string) => log.filter((e) => e === entry).length;

/** Open the row's dropdown and return the Delete item. Row-scoped by necessity:
 *  `More actions` repeats per row and the menu has no role to select on. */
async function openDeleteItem(page: Parameters<typeof login>[0], rowId: string) {
  const row = page.getByTestId(`webhook-row-${rowId}`);
  await expect(row).toBeVisible();
  await row.getByRole('button', { name: 'More actions', exact: true }).click();
  const item = row.getByRole('button', { name: 'Delete', exact: true });
  await expect(item).toBeVisible();
  return item;
}

test.describe('DO-4 delete a webhook through the native confirm (F-248)', () => {
  test('dismissing the confirm fires nothing; accepting it deletes, repaints, and restores', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);
    const log = watchRequests(page);
    const before = await webhookIds(api);

    let id = '';
    let deletedThroughUi = false;
    try {
      id = await createWebhook(api, ROW_NAME);
      const stored = await api.getJson(`${WEBHOOKS_URL}/${id}`);
      expect(stored.status, 'the row exists before the UI touches it').toBe(200);
      const storedName = String(stored.body?.name);

      await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
      const row = page.getByTestId(`webhook-row-${id}`);
      await expect(row).toBeVisible();

      // ---- ARM 1: dismiss. The contract is an ABSENCE, anchored three ways. ----
      // waitForEvent, NOT page.once('dialog', async d => …): the click resolves as
      // soon as the pointer action lands, so a fire-and-forget handler may not have
      // run yet when the next line reads its capture — and an empty captured message
      // would then read as "the app never asked", i.e. a false accusation against the
      // page for a race in the spec. Awaiting the event makes the message a fact.
      const dismissPrompt = page.waitForEvent('dialog');
      await (await openDeleteItem(page, id)).click();
      const dismissed = await dismissPrompt;

      // The exact shipped template (WebhooksPage.tsx:200), carrying THIS row's stored
      // name. If the app ever switched to an in-app modal there is no dialog and
      // waitForEvent times out naming exactly that — loud, never vacuous.
      expect(dismissed.type(), 'the prompt is the browser-native confirm').toBe('confirm');
      expect(dismissed.message(), 'the native prompt carries the row name').toBe(
        `Are you sure you want to delete "${storedName}"?`
      );
      await dismissed.dismiss();
      const deletePath = `DELETE ${WEBHOOKS_URL}/${id}`;
      expect(countOf(log, deletePath), 'a dismissed confirm sends no DELETE').toBe(0);
      await expect(row, 'the row survives a dismissed confirm').toBeVisible();
      expect(await webhookIds(api), 'and the store still has it').toContain(id);

      // ---- ARM 2: accept. The only leg that touches the network. ----
      const listGetsBefore = countOf(log, `GET ${WEBHOOKS_URL}`);
      const healthGetsBefore = countOf(log, `GET ${WEBHOOKS_URL}/health`);

      const acceptPrompt = page.waitForEvent('dialog');
      await (await openDeleteItem(page, id)).click();
      const accepted = await acceptPrompt;
      expect(accepted.message(), 'the prompt is the same template the first time').toBe(
        `Are you sure you want to delete "${storedName}"?`
      );

      // Armed BEFORE accept(): the DELETE goes out the instant the page's await of
      // confirm() resolves, so a matcher armed after accept() can already have missed
      // it and waitForResponse then fails for the wrong reason.
      const deleted = page
        .waitForResponse(
          (r) => apiPath(r.url()) === `${WEBHOOKS_URL}/${id}` && r.request().method() === 'DELETE'
        )
        .then((r) => r.status());
      await accepted.accept();

      // 204 with NO body (outbound_webhooks.py:500-502): webhookApi.ts:103-105 must
      // return before parsing, so a naive response.json() here surfaces as this leg.
      expect(await deleted, 'the accept DELETEs and answers 204').toBe(204);
      deletedThroughUi = true;

      // The row's removal is a refetch, not a local splice.
      await expect
        .poll(() => countOf(log, `GET ${WEBHOOKS_URL}`) > listGetsBefore, {
          message: 'the list refetch is what removes the row',
        })
        .toBe(true);
      await expect
        .poll(() => countOf(log, `GET ${WEBHOOKS_URL}/health`) > healthGetsBefore, {
          message: 'the delete also invalidates the health card (useWebhooks.ts:639-652)',
        })
        .toBe(true);

      await expect(page.getByTestId(`webhook-row-${id}`), 'the row is gone').toHaveCount(0);
      expect(await webhookIds(api), 'the store agrees').not.toContain(id);
    } finally {
      // Teardown must not double-delete: the accept arm already removed the row, and
      // deleteWebhook asserts a 204 that a second call cannot return.
      if (id && !deletedThroughUi && (await webhookIds(api)).includes(id)) {
        await deleteWebhook(api, id);
      }
    }

    expect(await webhookIds(api), 'the stack is exactly as this spec found it').toEqual(before);
  });

  test('the guard survives the native-dialog drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('webhooks-page')).toBeVisible();
    // Proves page.once('dialog') did not require, and does not license, any route
    // interception: the tripwire still throws the same message.
    await assertGuardSurvives(page, h);
  });
});
