/**
 * F2.3 DO-4 golden path — F-249, the Test webhook modal.
 *
 * Inventory row (F-249): "clicks Test; picks an event type; sees status code, response
 * time and body", over `POST /api/outbound-webhooks/{webhook_id}/test`.
 *
 * Which arm of this row is provable here, and why the other one is not faked:
 * - The modal has two outcomes and they are different claims. `success` is
 *   `200 <= status_code < 300` on the real outbound POST (webhook_service.py:589); a
 *   connection that never established raises httpx.RequestError and returns
 *   success=false with status_code=None and response_time_ms=None (:599-603), which the
 *   modal paints as the literal `N/A` in BOTH detail cells (WebhookTestModal.tsx:89, :101).
 * - The SUCCESS arm needs an HTTP 2xx target the fake stack does not have: compose
 *   publishes only ai-vlm:8098 and ai-gateway:8090 (docker-compose.fake-ai.yml:69-70,
 *   :97-98), there is no webhook seeding anywhere in it (grep -rin webhook
 *   docker-compose.fake-ai.yml docker/fake-ai → empty), and ruling 87 keeps this PR out
 *   of compose and the harness. So this spec drives the REFUSAL — the same deterministic
 *   sink the backend's own golden spec uses (test_webhook_deliveries.py:68, and :20
 *   explains the choice: httpx fails it in milliseconds, so no retry window is waited
 *   out) — and the 2xx arm is left for the real tier, which is exactly where F2.1 says a
 *   number you cannot produce unmocked belongs. Stubbing a 200 would be a `page.route`,
 *   which the guard throws on (guard.ts:46).
 * - Census before writing: `N/A` occurs 3× on this mount (twice in the result block,
 *   once as the health card's Avg Response), so the two are asserted as a COUNT scoped to
 *   [data-testid=test-result]. "count is 2" is the stronger claim anyway — it is what
 *   "both detail cells fell to their empty form" means.
 *
 * The second contract this file pins is the one the row states in its own evidence: the
 * test creates NO delivery record (webhookApi.ts:245-249, useWebhooks.ts:694-698 — which
 * is also why the test mutation invalidates nothing). The proof is an API read of
 * `total_deliveries` on the row, before and after a send that really went out and really
 * failed: still 0. A UI-only spec could never see that, and a spec that asserted the
 * counter stayed 0 without sending anything would be vacuous — the send is witnessed on
 * the network first.
 *
 * Event-picker contract: the picker is a NATIVE <select id="test-event-type">
 * (WebhookTestModal.tsx:202-213), not a listbox, initialised to 'alert_fired' (:140) —
 * initialised PER PAGE MOUNT, not per open, because the component is mounted
 * unconditionally and never unmounts (see the last leg, which pins what that means for a
 * reopening user) — and
 * the option text comes from WEBHOOK_EVENT_LABELS (:322-323) — so the spec selects by
 * LABEL ('Alert Dismissed') and asserts the request BODY carries the wire value
 * ('alert_dismissed'). That label→value translation is a UI-only contract: the API-only
 * backend spec cannot see it, and a spec that set the value directly would not test it.
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

const ROW_NAME = 'DO-4 f249 test row';
const TEST_PATH = (id: string) => `${WEBHOOKS_URL}/${id}/test`;

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

/** total_deliveries as the STORE has it — the number the modal cannot move. */
async function deliveriesOf(api: Awaited<ReturnType<typeof authedFetch>>, id: string) {
  const res = await api.getJson(`${WEBHOOKS_URL}/${id}`);
  expect(res.status, 'the row is readable by id').toBe(200);
  return Number(res.body?.total_deliveries ?? -1);
}

function watchRequests(page: Parameters<typeof login>[0]): string[] {
  const log: string[] = [];
  page.on('request', (req) => log.push(`${req.method()} ${apiPath(req.url())}`));
  return log;
}

const countOf = (log: string[], entry: string) => log.filter((e) => e === entry).length;

test.describe('DO-4 Test webhook modal (F-249)', () => {
  test('the modal sends the picked event type, reports a refused target honestly, and records nothing', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);
    const before = await webhookIds(api);
    // Independent channel for "which request went out" — see the assert below.
    const log = watchRequests(page);

    let id = '';
    try {
      id = await createWebhook(api, ROW_NAME);
      expect(await deliveriesOf(api, id), 'a fresh row has no deliveries').toBe(0);

      await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
      const row = page.getByTestId(`webhook-row-${id}`);
      await expect(row).toBeVisible();

      // Open through the ROW's icon button — accessible name is the shipped template
      // `Test ${webhook.name}` (WebhookList.tsx:378), which makes it row-unique.
      await row.getByRole('button', { name: `Test ${ROW_NAME}`, exact: true }).click();

      const dialog = page.getByRole('dialog', { name: 'Test Webhook', exact: true });
      await expect(dialog).toBeVisible();
      // Subtitle carries the row's own name and URL (:188-191).
      await expect(dialog.getByText(ROW_NAME, { exact: true })).toBeVisible();

      // Native select, default from React state (:140) — NOT from the API.
      const picker = dialog.getByLabel('Event Type', { exact: true });
      await expect(picker).toHaveValue('alert_fired');

      // Pick a DIFFERENT type by its human label; the wire value is asserted on the
      // request body below, which is the only place the translation is observable.
      await picker.selectOption({ label: 'Alert Dismissed' });
      await expect(picker).toHaveValue('alert_dismissed');

      // NB: `method`/`path` are NOT harvested here any more, and that is deliberate.
      // The predicate below is what `waitForResponse` resolves on, so every value the
      // predicate compared is a CONSTANT by the time the `.then` runs — an assertion on
      // `res.method`/`res.path` can only ever pass. An earlier revision of this leg did
      // exactly that while its message claimed to be "checking which request it was".
      // Which request went out is measured independently, from `log` below.
      const sent = page
        .waitForResponse(
          (r) => apiPath(r.url()) === TEST_PATH(id) && r.request().method() === 'POST'
        )
        .then(async (r) => ({
          status: r.status(),
          // postDataJSON() IS NOT A PROMISE — it is `postDataJSON(): null|Serializable`
          // (playwright-core types.d.ts:22369), and the returned value is what the
          // browser actually sent. An earlier draft wrote `.postDataJSON().catch(()=>null)`
          // and it typechecked clean under this repo's strict tsc, because
          // `Serializable` is declared `export type Serializable = any` (types/structs.d.ts:22),
          // so `null | any` collapses to any and `.catch` on it is legal. At runtime it
          // threw `TypeError: … .catch is not a function` and took the test down. Two
          // lessons, both kept here deliberately: a promise-shaped chain is not proof of
          // a promise, and strict mode cannot see through a `= any` alias. So: no
          // `.catch`, and nothing that could turn "no body" into a silent undefined.
          body: r.request().postDataJSON() as { event_type?: string } | null,
          json: await r.json().catch(() => null),
        }));

      await dialog.getByRole('button', { name: 'Send Test', exact: true }).click();
      const res = await sent;

      // The route answers 200 even for a FAILED test — it has no status_code override
      // and returns the WebhookTestResponse body (outbound_webhooks.py:550-563); the
      // only failure it raises is 404 for a missing row. Asserting 200 here pins that,
      // so a later "make failures 4xx" change fails LOUD instead of silently changing
      // what the modal's error block means.
      expect(res.status, 'the test route answers 200 and reports failure in the body').toBe(200);
      expect(res.body?.event_type, 'label → wire value reaches the body').toBe('alert_dismissed');
      // This literal is the whole point of the leg: a page-wide request counter
      // matching only "POST /api/outbound-webhooks/" would also be satisfied by an
      // enable or a delete, so the witness names the suffix. It is counted from `log`
      // — the browser's own request stream — and NOT from the response the matcher
      // resolved on: `waitForResponse` only resolves when its predicate holds, so
      // method+path read off that response are constants and a count-free assert on them
      // is a tautology wearing a message. (An earlier revision did exactly that; the
      // comment above the retired line already recorded the same class of bug one level
      // down, which is the tell that reading your own assert messages is not the same as
      // reading your own asserts.) Exactly one test send, and the log can show zero.
      expect(countOf(log, `POST ${TEST_PATH(id)}`), 'exactly one test send went out').toBe(1);

      // The refusal, reported rather than swallowed.
      expect(res.json?.success, 'a refused target is not a pass').toBe(false);
      expect(res.json?.status_code, 'nothing answered, so no status code').toBeNull();

      const result = page.getByTestId('test-result');
      await expect(result).toBeVisible();
      await expect(result.getByText('Test Failed', { exact: true })).toBeVisible();
      await expect(result.getByText('Response Code', { exact: true })).toBeVisible();
      await expect(result.getByText('Response Time', { exact: true })).toBeVisible();
      // Census-pinned: EXACTLY the two empty-form cells inside the result block, and
      // only inside it — a page-wide locator would bind the health card's Avg Response
      // too (3× on this mount) and strict-mode.
      await expect(result.getByText('N/A', { exact: true })).toHaveCount(2);
      await expect(result.getByText('Error', { exact: true })).toBeVisible();
      // The message is httpx's own (webhook_service.py:602 `str(e)[:500]`), so match the
      // family of connection-refusal wording rather than pinning one library's sentence.
      await expect(result.getByText(/refused|unable to connect|connection/i).first()).toBeVisible();
      // No response body exists to show, so that block must not render at all (:114-122).
      await expect(result.getByText('Response Body (truncated)', { exact: true })).toHaveCount(0);

      // THE ROW'S OWN CLAIM: a test writes no delivery record. The send demonstrably
      // happened (witnessed above), so a counter that is still 0 is evidence, not a
      // skipped loop.
      expect(await deliveriesOf(api, id), 'a test POST creates no delivery row').toBe(0);

      // Close hides the modal and clears the RESULT state, so no stale verdict
      // survives — measured, and true.
      await dialog.getByRole('button', { name: 'Close', exact: true }).click();
      await expect(page.getByRole('dialog', { name: 'Test Webhook', exact: true })).toHaveCount(0);
      await row.getByRole('button', { name: `Test ${ROW_NAME}`, exact: true }).click();
      const again = page.getByRole('dialog', { name: 'Test Webhook', exact: true });
      await expect(again).toBeVisible();
      await expect(page.getByTestId('test-result'), 'no stale result survives Close').toHaveCount(
        0
      );
      // BUT THE PICK DOES NOT RESET, and this assertion pins that — not the
      // 'alert_fired' this leg originally expected, which the first live run refuted
      // (`Expected: "alert_fired"  Received: "alert_dismissed"`). The mechanism is
      // structural: WebhookTestModal is mounted UNCONDITIONALLY (WebhooksPage.tsx:369;
      // `isOpen={testingWebhook !== null}` gates only rendering inside, so the component
      // never unmounts), and `useState('alert_fired')` (:140) therefore initialises once
      // per PAGE mount. handleClose (:146-151) resets testResult/testError/isTesting and
      // its comment claims "Reset state when modal opens/closes", but it never touches
      // selectedEventType and the file has no useEffect at all. So the comment
      // overreaches and the shipped behaviour is: the event type sticks until reload.
      // Pinning the real behaviour rather than the wished-for one, because a golden path
      // records what the app does — and if frontend later adds the reset the comment
      // promises, THIS line goes red, which is the loud signal that a documented
      // behaviour changed. Discrepancy reported to the reviewing lane in the PR body.
      await expect(again.getByLabel('Event Type', { exact: true })).toHaveValue('alert_dismissed');
    } finally {
      if (id) await deleteWebhook(api, id);
    }

    expect(await webhookIds(api), 'the stack is exactly as this spec found it').toEqual(before);
  });

  test('the guard survives the test-modal drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('webhooks-page')).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});
