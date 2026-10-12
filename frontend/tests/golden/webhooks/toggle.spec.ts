/**
 * F2.3 DO-4 golden path — F-247, the enable/disable switch.
 *
 * Inventory row (F-247): "flips the enabled toggle on a webhook", over
 * `POST /api/outbound-webhooks/{id}/enable` + `.../disable`.
 *
 * Three laws, all read at this head:
 *
 * - THE SWITCH IS NOT NAMED PER ROW. aria-label is the fixed string
 *   'Disable webhook' / 'Enable webhook' (WebhookList.tsx:336) — it never carries the
 *   webhook's name — so two enabled rows carry the SAME accessible name and a
 *   page-wide getByRole('switch', {name:'Disable webhook'}) strict-modes. That is not a
 *   test nitpick, it is the shipped accessibility contract, so the second test here
 *   asserts the collision (count 2) instead of working around it silently. Every
 *   toggle locator in this file is row-scoped for exactly that reason.
 * - NOTHING MOVES UNTIL THE REFETCH COMES BACK. There are no optimistic updates on
 *   this page: `grep -n "onMutate|cancelQueries|setQueryData|rollbackOn"
 *   frontend/src/hooks/useWebhooks.ts` → 0 hits, while the file's own header comment
 *   (:25) claims "Optimistic updates where appropriate". The mutation's onSuccess only
 *   invalidates ['webhooks','list'], ['webhooks','detail',id] and ['webhooks','health']
 *   (useWebhooks.ts:789-802). So the visible flip is a re-render off a fresh GET, and
 *   this file WITNESSES that GET after the POST rather than trusting the mutation
 *   response — a spec that awaited only the POST would pass against a UI that forgot to
 *   repaint.
 * - THE DISPATCH IS DIRECTIONAL. mutationFn sends enable when the requested `enabled`
 *   is true and disable when false (useWebhooks.ts:787-788), and the page always passes
 *   `!webhook.enabled` (WebhooksPage.tsx:341 via onToggle), so clicking an ENABLED row
 *   must produce a `/disable` and never a `/enable`. Both verbs are witnessed with
 *   apiPath EQUALITY (harness.ts:236-255): a suffix match would let a `/enable` satisfy
 *   an expectation about `/disable`'s prefix and the test would measure nothing.
 *
 * The row is created enabled (harness.ts:216-235) so the flip direction is fixed by
 * construction rather than by whatever the API default happens to be — the schema
 * default IS true (api/schemas/outbound_webhook.py:152) but a spec that leans on an
 * unasserted default is how a silent inversion survives review.
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

const ROW_NAME = 'DO-4 f247 toggle row';
const SECOND_ROW = 'DO-4 f247 second row';

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

/** Every request the page makes, recorded as "METHOD path". Recorded rather than
 *  awaited through a predicate so an ABSENCE ("no /enable fired") is assertable — the
 *  one thing a waitForResponse can never show you. */
function watchRequests(page: Parameters<typeof login>[0]): string[] {
  const log: string[] = [];
  page.on('request', (req) => log.push(`${req.method()} ${apiPath(req.url())}`));
  return log;
}

const countOf = (log: string[], entry: string) => log.filter((e) => e === entry).length;

async function enabledOf(api: Awaited<ReturnType<typeof authedFetch>>, id: string) {
  const res = await api.getJson(`${WEBHOOKS_URL}/${id}`);
  expect(res.status, 'the row is readable by id').toBe(200);
  return res.body?.enabled;
}

test.describe('DO-4 enable/disable switch (F-247)', () => {
  test('one click disables through the API and repaints off the refetch, and a second restores it', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);
    const log = watchRequests(page);
    const before = await webhookIds(api);

    let id = '';
    try {
      id = await createWebhook(api, ROW_NAME);
      expect(await enabledOf(api, id), 'the fixture row starts enabled').toBe(true);

      await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
      const row = page.getByTestId(`webhook-row-${id}`);
      const sw = row.getByRole('switch');
      await expect(sw).toHaveAttribute('aria-checked', 'true');
      await expect(sw).toHaveAccessibleName('Disable webhook');

      const getListBefore = countOf(log, `GET ${WEBHOOKS_URL}`);

      // --- click an ENABLED row: the only admissible request is /disable ---
      const postDisable = page
        .waitForResponse(
          (r) =>
            apiPath(r.url()) === `${WEBHOOKS_URL}/${id}/disable` && r.request().method() === 'POST'
        )
        .then((r) => r.status());
      await sw.click();
      expect(await postDisable, 'disabling POSTs /disable (200)').toBe(200);

      // The repaint is a refetch, not an optimistic write: the list GET count grows.
      await expect
        .poll(() => countOf(log, `GET ${WEBHOOKS_URL}`) > getListBefore, {
          message: 'the switch repaint is driven by a list refetch, not an optimistic update',
        })
        .toBe(true);

      await expect(sw, 'aria-checked follows the store').toHaveAttribute('aria-checked', 'false');
      await expect(sw, 'the accessible name flips too').toHaveAccessibleName('Enable webhook');
      expect(await enabledOf(api, id), 'the store really holds enabled=false').toBe(false);

      // --- second click restores: the direction must invert, not repeat ---
      const postEnable = page
        .waitForResponse(
          (r) =>
            apiPath(r.url()) === `${WEBHOOKS_URL}/${id}/enable` && r.request().method() === 'POST'
        )
        .then((r) => r.status());
      await sw.click();
      expect(await postEnable, 're-enabling POSTs /enable (200)').toBe(200);
      await expect(sw).toHaveAttribute('aria-checked', 'true');
      expect(await enabledOf(api, id), 'the row is back the way I found it').toBe(true);

      // The verb the page must NEVER send for this row's first click.
      expect(countOf(log, `POST ${WEBHOOKS_URL}/${id}/enable`), 'one /enable, the restore').toBe(1);
      expect(countOf(log, `POST ${WEBHOOKS_URL}/${id}/disable`), 'one /disable, the flip').toBe(1);
    } finally {
      if (id) await deleteWebhook(api, id);
    }

    expect(await webhookIds(api), 'the stack is exactly as this spec found it').toEqual(before);
  });

  test('two enabled rows carry the SAME switch name — row scope is mandatory', async ({ page }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);
    const before = await webhookIds(api);
    const ids: string[] = [];
    try {
      ids.push(await createWebhook(api, ROW_NAME), await createWebhook(api, SECOND_ROW));
      await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });

      // The shipped contract: the name is a constant (WebhookList.tsx:336), so a
      // page-wide locator for it binds BOTH rows. Counting them is the assertion; a
      // locator that "worked" here would be bound to one row by accident of ordering.
      await expect(
        page.getByRole('switch', { name: 'Disable webhook', exact: true }),
        'the accessible name is not row-unique'
      ).toHaveCount(2);

      // Row scope resolves it, and the two rows are independently addressable.
      for (const id of ids) {
        await expect(page.getByTestId(`webhook-row-${id}`).getByRole('switch')).toHaveAttribute(
          'aria-checked',
          'true'
        );
      }
    } finally {
      for (const id of ids) await deleteWebhook(api, id);
    }
    expect(await webhookIds(api), 'both rows restored').toEqual(before);
  });

  test('the guard survives the toggle drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('webhooks-page')).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});
