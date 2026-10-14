/**
 * F2.3 DO-4 golden path — F-248, delete a webhook and confirm.
 *
 * Inventory row (F-248): "clicks Delete on a webhook and confirms", over
 * `DELETE /api/outbound-webhooks/{webhook_id}`.
 *
 * THE DIALOG IS NATIVE, AND THAT IS A FIRST IN THIS TREE.
 * WebhooksPage.tsx:200 confirms with `window.confirm(...)`, not an in-app modal.
 * Measured at the BASELINE this batch branches from (`git grep -n -E
 * "on\('dialog'|waitForEvent\('dialog'|runAndWaitForDialog" origin/main --
 * frontend/tests/` → no hits; the same search over frontend/tests/e2e/ → none), so
 * there is no precedent to copy here and no prior art to trust. (Stated against the
 * baseline, not "this head", because this file is the first hit — a census quoted at
 * your own head is measuring your own edit.) What this file uses is one answering
 * `page.on('dialog')` handler — see `answerConfirm` for why a *waiter* deadlocks and
 * only a handler works. That is the
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
 * Locator cardinality counted on this mount: 'More actions' is 1× per row (the trigger's
 * aria-label, WebhookList.tsx:175), and the menu it opens holds FOUR <button>s in the div
 * at :188-222 — Test Webhook (:189), View Deliveries (:197), Edit (:205), Delete (:214) —
 * each named by its own text child, which is why :141's
 * `getByRole('button', { name: 'Delete', exact: true })` resolves at all. An earlier
 * revision of this paragraph said "three", and the count agreed with it because the window
 * it quoted started at :196 — Test Webhook's CLOSING tag — so the grep silently dropped
 * that item's opening tag. A window cite agrees with its own prose by construction; print
 * the span. A grep over the two mounted files that render the surface finds 'Delete' 14×
 * (WebhookList.tsx 8 + WebhooksPage.tsx 6) — but do NOT read that as the strict-mode risk,
 * because an earlier revision did and labelled those hits "mostly JSDoc", which the
 * enumeration refutes: 12 are identifier SUBSTRINGS (`onDelete`, `useDeleteWebhook`,
 * `handleDelete`), 1 is a comment (WebhooksPage.tsx:197), and 1 is rendered text. A
 * substring match in source is invisible to getByText. The number that actually governs is
 * that last one: 'Delete' renders exactly ONCE per row, as a JSX text child (:220, beside
 * a <Trash2> icon) — so a page-wide getByText('Delete') binds one node per visible row and
 * strict-modes the moment the table has two. That, not the grep total, is why every locator
 * in this file is row-scoped. Count in the unit the instrument reads: grep counts
 * occurrences in source, getByText counts nodes in the DOM.
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

/** Answer the page's native confirm AND capture what it said, in one handler.
 *
 * WHY THIS SHAPE, MEASURED (local --fake run hsi-check-20261012232348-cd7908). My first
 * version used `page.waitForEvent('dialog')` and awaited the click, then dismissed. That
 * DEADLOCKS, and the reason is the thing to know about native dialogs:
 * registering ANY dialog listener suppresses Playwright's auto-dismiss, and
 * `window.confirm` blocks the page's JS main thread until it is answered. So the confirm
 * sat open, the click could never finish dispatching, and the click timed out at 5000 ms
 * (`locator.click: Timeout … performing click action`) BEFORE the line that would have
 * dismissed it ever ran. The waiter observes the dialog; only a handler ANSWERS it.
 *
 * That also retires the race an earlier draft of this file worried about (that a
 * fire-and-forget handler might not have recorded its message before the next line read
 * it): the capture happens inside the handler, synchronously, and the page thread cannot
 * resume until the handler has answered — so by the time the click resolves, the message
 * is already recorded. No race to lose, and nothing is read fire-and-forget.
 *
 * The decision is mutable because the arms differ (dismiss, then accept). A stray dialog
 * would get the currently-armed answer instead of Playwright's default, which is why each
 * arm asserts the running TOTAL (`toHaveLength(1)`, then `toHaveLength(2)`): an
 * unexpected confirm shows up as a wrong count rather than being silently absorbed, and a
 * handler that never fired fails the first arm loudly instead of letting the DELETE-
 * absence assertion pass for no reason at all. */
function answerConfirm(page: Parameters<typeof login>[0]): {
  prompts: { type: string; message: string }[];
  setDecision: (d: 'dismiss' | 'accept') => void;
} {
  const prompts: { type: string; message: string }[] = [];
  let decision: 'dismiss' | 'accept' = 'dismiss';
  page.on('dialog', (dialog) => {
    prompts.push({ type: dialog.type(), message: dialog.message() });
    // Deliberately not awaited: answering IS what unblocks the click we are awaiting.
    void (decision === 'dismiss' ? dialog.dismiss() : dialog.accept());
  });
  return { prompts, setDecision: (d) => (decision = d) };
}

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
      const confirm = answerConfirm(page);
      await (await openDeleteItem(page, id)).click();

      // Asserted from the handler's capture, which is already complete (the handler
      // answered, so the page thread resumed, so the click resolved). A non-null check
      // comes FIRST because the arms below are ABSENCES: if the handler never fired
      // there was no prompt, and `0 DELETEs` would pass for the wrong reason — a spec
      // bug reading as the feature working. This is the vacuity the notify-access
      // harness warns about (notify-access/harness.ts:240-251): an absence needs a
      // positive anchor that cannot hold when the cause is missing.
      expect(confirm.prompts, 'the page raised exactly one prompt').toHaveLength(1);
      const [dismissed] = confirm.prompts;
      // The exact shipped template (WebhooksPage.tsx:200), carrying THIS row's stored
      // name. If the app ever switched to an in-app modal there is no dialog and the
      // line above fails naming exactly that — loud, never vacuous.
      expect(dismissed.type, 'the prompt is the browser-native confirm').toBe('confirm');
      expect(dismissed.message, 'the native prompt carries the row name').toBe(
        `Are you sure you want to delete "${storedName}"?`
      );
      const deletePath = `DELETE ${WEBHOOKS_URL}/${id}`;
      expect(countOf(log, deletePath), 'a dismissed confirm sends no DELETE').toBe(0);
      await expect(row, 'the row survives a dismissed confirm').toBeVisible();
      expect(await webhookIds(api), 'and the store still has it').toContain(id);

      // ---- ARM 2: accept. The only leg that touches the network. ----
      const listGetsBefore = countOf(log, `GET ${WEBHOOKS_URL}`);
      const healthGetsBefore = countOf(log, `GET ${WEBHOOKS_URL}/health`);

      // Armed BEFORE THE CLICK — the earlier "arm before accept()" ordering is a
      // leftover of the waitForEvent shape and is now WRONG: the handler calls accept()
      // itself, mid-click, so the DELETE is in flight before this line could run in the
      // old position. Same rule, one step earlier: arm the matcher before the thing that
      // releases the request.
      const deleted = page
        .waitForResponse(
          (r) => apiPath(r.url()) === `${WEBHOOKS_URL}/${id}` && r.request().method() === 'DELETE'
        )
        .then((r) => r.status());

      confirm.setDecision('accept');
      await (await openDeleteItem(page, id)).click();
      confirm.setDecision('dismiss');

      expect(confirm.prompts, 'the second attempt also prompted').toHaveLength(2);
      expect(confirm.prompts[1].message, 'the prompt is the same template the first time').toBe(
        `Are you sure you want to delete "${storedName}"?`
      );

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
