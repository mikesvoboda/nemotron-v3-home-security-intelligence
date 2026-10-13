/**
 * F2.3 DO-4 golden path — F-245, the webhook list and its health card.
 *
 * Inventory row (docs/reference/feature-inventory.md §3.11, F-245): "opens Webhooks;
 * sees each outbound webhook (integration type, events, success rate, last delivery)
 * and a 24 h health summary", over `GET /api/outbound-webhooks` + `GET
 * /api/outbound-webhooks/health`.
 *
 * What this file proves, and the one thing it proves ABSENT:
 *
 * - The list renders a row the BACKEND has, not one the spec imagined: the API leg
 *   creates the row first (`createWebhook`, harness.ts:192-209) and the row's own fields read off
 *   the create response — the DOM is asserted against the API's echo, never against
 *   the literal I typed, because `url` is a pydantic `HttpUrl`
 *   (api/schemas/outbound_webhook.py:145) and whatever normalization it applies is
 *   exactly the kind of assumption a golden path must not carry silently.
 * - Both GETs the row names are WITNESSED on the browser's own network, with apiPath
 *   EQUALITY (`apiPath`, harness.ts:155-158 — a matcher that cannot match is worse than a wrong
 *   assert: it makes a "requested" list empty for the wrong reason and then
 *   toEqual([...]) passes vacuously).
 * - Success rate renders its EMPTY form. `webhook.total_deliveries > 0` gates the
 *   badge and the `(n/m)` pair (WebhookList.tsx:356-365), the column defaults to 0 at
 *   the DB layer (models/outbound_webhook.py:187-188), and the fake CI stack seeds no
 *   webhook and no delivery (grep -rin webhook docker-compose.fake-ai.yml docker/fake-ai:
 *   empty). So `No deliveries` is the only reachable state here, and the guard makes
 *   stubbing it away illegal (guard.ts:46). The 24 h tile likewise shows `No
 *   deliveries` and Avg Response `N/A` (WebhookHealthCard.tsx:157-184) — those are
 *   pinned too, because they are what a clean stack really shows.
 * - ABSENT, and this is a claim repair: the row says the user sees "last delivery",
 *   but `last_delivery_at`/`last_delivery_status` are never rendered on this surface.
 *   Measured at this head: `grep -rn last_delivery frontend/src/components/webhooks/
 *   frontend/src/pages/WebhooksPage.tsx` → 0 hits, and across all of frontend/src the
 *   token appears ONLY in types/generated/api.ts and types/webhook.ts:133,135 — i.e.
 *   it is on the wire type and nowhere in the markup. The control in the same grep
 *   family: `total_deliveries` returns 5 matching LINES in that same scope
 *   (WebhookList.tsx:356,360 + WebhookHealthCard.tsx:103,104,160 — lines, per
 *   `grep -rn | wc -l`; :104 holds the token twice, so an OCCURRENCE count is 6), so the
 *   instrument demonstrably
 *   fires when a token IS rendered there. (An earlier revision of this line said 9 and
 *   was never reproducible — the number drifted from a different scope than the one the
 *   sentence names. A control you cannot re-run in the scope it is quoted in is not a
 *   control.) The leg below pins the absence so the inventory cannot drift back.
 *
 * Locator cardinality, counted on this mount before writing (grep -o over
 * WebhooksPage.tsx + WebhookList.tsx + WebhookHealthCard.tsx + WebhookTestModal.tsx —
 * the modal counts because it is mounted UNCONDITIONALLY, and it is the fourth file the
 * /webhooks route renders; the file named here in an earlier revision, `EmptyState.tsx`,
 * is not in components/webhooks/ at all — it is components/common/EmptyState.tsx, so that
 * grep silently read a nonexistent path):
 * "No deliveries" occurs 2× (the row cell AND the health card) and "N/A" 3× (twice in
 * the test modal, once as Avg Response) — so EVERY one of those strings is scoped here
 * (row testid / card testid), never page-wide, or Playwright strict mode kills the
 * assert. "Webhook Health" is 1×. The health card's six stats are plain <p>s with no
 * roles (WebhookHealthCard.tsx:58-60), so getByText scoped inside the card is the whole
 * evidence surface for the summary.
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

/** Unique to this spec: no seeded fixture carries it, and the row's name cell is the
 *  handle every row-scoped locator in DO-4 keys off. */
const ROW_NAME = 'DO-4 f245 list row';

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

/** Both list-page GETs, witnessed rather than assumed. */
function watchWebhookGets(page: Parameters<typeof login>[0]): string[] {
  const seen: string[] = [];
  page.on('request', (req) => {
    if (req.method() !== 'GET') return;
    const path = apiPath(req.url());
    if (path === WEBHOOKS_URL || path === `${WEBHOOKS_URL}/health`) seen.push(path);
  });
  return seen;
}

test.describe('DO-4 webhook list + health card (F-245)', () => {
  test('the list renders the row the API has, and the health card counts it', async ({ page }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);
    const seen = watchWebhookGets(page);

    const before = await webhookIds(api); // API leg FIRST: a blank screen can
    let id = ''; // never pass as "the list renders".
    try {
      id = await createWebhook(api, ROW_NAME);
      const created = await api.getJson(`${WEBHOOKS_URL}/${id}`);
      expect(created.status, 'the row is readable by id').toBe(200);

      await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('webhooks-page')).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Webhooks', exact: true })).toBeVisible();

      // THE GETs THE ROW NAMES are the requests the browser actually made.
      await expect
        .poll(() => seen.filter((p) => p === WEBHOOKS_URL).length, {
          message: 'the page GETs /api/outbound-webhooks',
        })
        .toBeGreaterThan(0);
      await expect
        .poll(() => seen.filter((p) => p === `${WEBHOOKS_URL}/health`).length, {
          message: 'the page GETs /api/outbound-webhooks/health',
        })
        .toBeGreaterThan(0);

      const row = page.getByTestId(`webhook-row-${id}`);
      await expect(row, 'the row the backend has is on the page').toBeVisible();
      // Name cell + integration label (WebhookList.tsx:310-313); the label comes from
      // INTEGRATION_INFO, and 'generic' paints "Generic Webhook" (types/webhook.ts:351).
      await expect(row.getByText(ROW_NAME, { exact: true })).toBeVisible();
      await expect(row.getByText('Generic Webhook', { exact: true })).toBeVisible();
      // URL cell (319-323) — asserted against the API echo, not my literal.
      await expect(row.getByText(String(created.body?.url), { exact: true })).toBeVisible();
      // Event badge: one event paints one badge, label from WEBHOOK_EVENT_LABELS
      // (:322 'alert_fired': 'Alert Fired'), and maxVisible=2 adds no "+N more" here.
      await expect(row.getByText('Alert Fired', { exact: true })).toBeVisible();
      // Success rate in its ONLY reachable form on a clean stack, row-scoped because
      // the health card paints the same string (census: 2× on this mount).
      await expect(row.getByText('No deliveries', { exact: true })).toBeVisible();
      // The row's switch is on: aria-checked is the state, and the accessible NAME is
      // 'Disable webhook' while enabled — not per-row unique, hence the row scope.
      await expect(row.getByRole('switch')).toHaveAttribute('aria-checked', 'true');

      // Header row + my row = 2 <tr>s when the stack had none; scoped to MY table so a
      // seeded stack cannot strict-mode this. The thead row is also a `row`, so the
      // count is webhooks+1 (WebhookList.tsx:271-292) — I assert MY row instead of a
      // total, which is the claim that survives seeding.
      const health = page.getByTestId('webhook-health-card');
      await expect(health).toBeVisible();
      await expect(
        health.getByRole('heading', { name: 'Webhook Health', exact: true })
      ).toBeVisible();
      const healthBody = await api.getJson(`${WEBHOOKS_URL}/health`);
      expect(healthBody.status, 'the health route answers 200').toBe(200);
      // Total counts every webhook on the stack, so the number comes from the API's own
      // response rather than a hard-coded 1 (seeding again). And it is bound to its
      // LABEL structurally, not taken with .first(): a bare getByText('2') on a card
      // whose six tiles are all small integers would pass on the WRONG TILE's number —
      // the count would be right for the wrong stat. StatItem renders <p>{label}</p>
      // then <p>{value}</p> as siblings (WebhookHealthCard.tsx:57-59), so the value is
      // exactly the first following <p>.
      const totalValue = health
        .getByText('Total', { exact: true })
        .locator('xpath=following-sibling::p[1]');
      await expect(totalValue, 'the Total tile paints the API total').toBeVisible();
      await expect(totalValue).toHaveText(String(healthBody.body?.total_webhooks));
      // Same binding for the sub-value, which is the enabled count in a fixed template
      // (`${enabled} enabled`, :134) — the one place the card distinguishes enabled
      // from total, so the row I created must be inside it.
      await expect(
        health
          .getByText('Total', { exact: true })
          .locator('xpath=following-sibling::p[2]')
          .filter({ hasText: 'enabled' })
      ).toContainText(String(healthBody.body?.enabled_webhooks));
      // 24 h summary + latency in their reachable forms (WebhookHealthCard.tsx:157-184),
      // card-scoped because the row cell paints the same "No deliveries" (census: 2×).
      await expect(health.getByText('No deliveries', { exact: true })).toBeVisible();
      // CONDITIONAL, so the condition was measured rather than assumed: an `if` that
      // never holds turns the assert inside it into dead code that reports as a pass.
      // Read at this head on the feature-check stack: the route returns
      // average_response_time_ms = null (JSON null, typeof "object"), so this branch
      // DOES execute — the `N/A` below really runs. If a future seed gives the stack a
      // real delivery, this branch stops running and the pin silently retires; that is
      // why the guard is here and not a bare unconditional assert.
      if (healthBody.body?.average_response_time_ms === null) {
        await expect(
          health.getByText('Avg Response', { exact: true }).locator('xpath=following-sibling::p[1]')
        ).toHaveText('N/A');
      }

      // CLAIM REPAIR: "last delivery" is not on this surface at all. An absence assert
      // is only a guard if it can fire, so this one was put to a live-stack control at
      // this head: plant `<div>Last delivery: 3 minutes ago</div>` into the real DOM and
      // re-count the SAME locator -> matched=1. The locator binds the text when the text
      // exists, so the 0 below is a measurement and not an untestable regex. (The plant
      // lived in a throwaway spec, run once, deleted; it asserts nothing about the app.)
      await expect(page.getByText(/last delivery/i)).toHaveCount(0);
    } finally {
      if (id) await deleteWebhook(api, id);
    }

    expect(await webhookIds(api), 'the stack is exactly as this spec found it').toEqual(before);
  });

  test('an empty stack says so, with no table', async ({ page }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);
    const ids = await webhookIds(api);
    // Loud skip, not a silent pass: on a stack that carries rows the empty branch is
    // unreachable, and pretending otherwise would make this test vacuous.
    test.skip(
      ids.length > 0,
      `stack already has ${ids.length} webhook(s) — empty state unreachable`
    );

    await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
    // EmptyState (WebhookList.tsx:252-262 → EmptyState.tsx): heading + description, and
    // NO action button — WebhookList passes no `actions`, so the EmptyState's own testid
    // is 'empty-state' and 'webhook-list' is NOT rendered.
    await expect(page.getByText('No Webhooks Configured', { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        'Create your first webhook to receive real-time notifications when events occur.',
        {
          exact: true,
        }
      )
    ).toBeVisible();
    await expect(
      page.getByTestId('webhook-list'),
      'the table unmounts when the list is empty'
    ).toHaveCount(0);
  });

  test('the guard survives the list and health-card drive', async ({ page }) => {
    const h = harness as Harness;
    await signIn(page, h);
    await page.goto(`${h.ui}/webhooks`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('webhooks-page')).toBeVisible();
    await assertGuardSurvives(page, h);
  });
});
