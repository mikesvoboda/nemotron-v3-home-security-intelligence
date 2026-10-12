/**
 * F-087 (inventory 3.6): the Trash page at /trash — soft-deleted events,
 * restore through the UI, bulk restore, and the permanent-delete confirmations
 * that must NOT delete anything here.
 *
 * The row's own evidence says the seed leg cannot come from the UI: "the only
 * writers of `deleted_at` are DELETE /api/events/{event_id} (events.py:2713)
 * and the bulk delete (:1780), and no frontend surface sends a soft delete."
 * So the spec seeds trash through exactly that cited writer (a node-side
 * DELETE — never intercepted; the guard bans routes, not real traffic) and
 * the golden path starts where a user's path starts: opening /trash and
 * finding the events there. Everything the restore legs do is real and fully
 * reversible — restoring returns the seeded events to the active list, which
 * the spec verifies at the end by node read. No permanent delete is ever
 * confirmed: both Delete-Forever confirmations click CANCEL, and an observer
 * proves the cancel produced no DELETE request at all.
 *
 * Mirrors follow the lane's observer idiom (F-184/OP-3): every asserted
 * number and string is taken from the body the PAGE itself received from
 * /api/events/deleted, not a node-side pre-read (two reads of a live list are
 * two moments). Node-side calls only prove endpoints and the final
 * post-restore state.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  apiCookie,
  authPost,
  closedByGuard,
  loginAsAdmin,
  readOpsHarness,
  type OpsHarness,
  type Session,
} from '../operations/harness';

const harness = readOpsHarness();

interface DeletedEvent {
  id: number;
  camera_id: string;
  summary: string | null;
  risk_score: number | null;
  deleted_at: string;
}

interface DeletedListBody {
  items: DeletedEvent[];
}

interface EventListBody {
  items: Array<{ id: number }>;
}

/** Seed one event into the trash via the row's cited only-writer (204). */
async function seedSoftDelete(h: OpsHarness, session: Session, id: number): Promise<void> {
  const res = await fetch(`${h.api}/api/events/${id}`, {
    method: 'DELETE',
    headers: apiCookie(session),
  });
  if (res.status !== 204) {
    throw new Error(`seed soft-delete ${id} answered ${res.status}: ${await res.text()}`);
  }
}

// Mirror of frontend/src/utils/risk.ts getRiskLevel + getRiskLabel (thresholds
// LOW 0-29 / MEDIUM 30-59 / HIGH 60-84 / CRITICAL 85-100, risk.ts:95-105,196).
// The card renders RiskBadge showScore, i.e. "Medium (54)" — the mirror lets
// the spec assert the badge from the API's own score rather than a snapshot.
function riskBadgeText(score: number): string {
  const level = score <= 29 ? 'Low' : score <= 59 ? 'Medium' : score <= 84 ? 'High' : 'Critical';
  return `${level} (${score})`;
}

test.describe('golden path: trash page restore flows @critical', () => {
  // Seed + reload + several mutation round-trips; 90 s like the F-184 spec.
  test.setTimeout(90_000);

  test('trash mirrors the deleted-events API, restores one and restores selected, and its delete confirmations delete nothing', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Backend legs: the trash list answers, and the active list has events to
    // seed from. (This node read picks SEEDS; it is deliberately not used for
    // any mirror — those come from the page's own fetch below.) A fresh CI
    // golden stack can boot with zero events, so the pool is guaranteed via
    // POST /api/admin/seed/events (non-destructive: clear_existing defaults
    // false; the lane's audit.spec.ts already seeds through this same admin
    // gate with this same session).
    // Precondition: the trash starts EMPTY so the exact-equality mirror below
    // is a mirror and not a race with foreign rows. On a fresh CI stack this
    // loop is a no-op; on a dev stack left dirty by an interrupted run it
    // restores the residue through the same cited restore endpoint (real,
    // non-destructive — the opposite of the permanent deletes this spec
    // pins as cancelled).
    const pre = await api<DeletedListBody>(h, session, '/api/events/deleted');
    for (const stale of pre.items) {
      await authPost<unknown>(h, session, `/api/events/${stale.id}/restore`, {});
    }
    let pool = await api<EventListBody>(h, session, '/api/events?limit=5');
    if (pool.items.length < 3) {
      await authPost<{ events_created: number }>(h, session, '/api/admin/seed/events', {
        count: 5,
      });
      pool = await api<EventListBody>(h, session, '/api/events?limit=5');
    }
    const seeds = pool.items.slice(0, 3).map((e) => e.id);
    expect(seeds.length).toBe(3);

    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));

    // Trash-list responses the PAGE itself fetches: each carries the URL and
    // a body promise. Every trash string asserted below is read from the
    // newest of these bodies.
    const trashFetches: Array<{ url: URL; body: Promise<DeletedListBody | null> }> = [];
    const restorePosts: Array<{ status: number }> = [];
    let deleteRequests = 0;
    page.on('response', (res) => {
      try {
        const url = new URL(res.url());
        if (url.pathname === '/api/events/deleted') {
          trashFetches.push({ url, body: res.json().catch(() => null) });
        } else if (
          res.request().method() === 'POST' &&
          /\/api\/events\/\d+\/restore$/.test(url.pathname)
        ) {
          restorePosts.push({ status: res.status() });
        } else if (
          res.request().method() === 'DELETE' &&
          /^\/api\/events\/\d+$/.test(url.pathname)
        ) {
          deleteRequests += 1;
        }
      } catch {
        /* non-URL-ish response — not our endpoint */
      }
    });

    // Seed: exactly the writer the inventory row cites as the only one.
    for (const id of seeds) await seedSoftDelete(h, session, id);

    const atSeed = trashFetches.length;
    await page.goto(`${h.ui}/trash`, { waitUntil: 'domcontentloaded' });
    await expect.poll(() => trashFetches.length).toBeGreaterThan(atSeed);
    const trashed = (await trashFetches[trashFetches.length - 1].body) as DeletedListBody;
    expect(trashed.items.map((e) => e.id).sort()).toEqual([...seeds].sort());
    expect(pageErrors).toEqual([]);

    // The page header renders even when populated, and the count line mirrors
    // the API's own list length ("3 events in trash" — spaces are JSX literal
    // text, not interpolation seams, so a plain substring is safe here).
    await expect(page.getByText(`${trashed.items.length} events in trash`)).toBeVisible();

    // Card mirrors from the page's body: camera heading, summary, risk badge,
    // and the relative "Deleted …" stamp (seeded seconds ago → "Just now";
    // the regex stays honest if the clock ticks a minute during the run).
    const first = trashed.items[0];
    const card = page.getByTestId(`deleted-event-card-${first.id}`);
    await expect(card).toBeVisible();
    await expect(card.locator('h3')).toHaveText(first.camera_id);
    if (first.summary) await expect(card).toContainText(first.summary);
    if (first.risk_score !== null) {
      await expect(card).toContainText(riskBadgeText(first.risk_score));
    }
    await expect(card).toContainText(/Deleted\s*(Just now|\d+ minutes? ago)/);

    // "refreshes": a reload re-boots the app, and the observer proves the new
    // mount fetched the trash list again (no refresh button exists on this
    // page — the row's clause is the page's own refetch mechanism).
    const beforeReload = trashFetches.length;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect.poll(() => trashFetches.length).toBeGreaterThan(beforeReload);

    // Header "Empty Trash" is enabled while items exist; its confirmation
    // mirrors the trash count; Cancel deletes nothing (DELETE observer frozen).
    const emptyTrash = page.getByTestId('empty-trash-button');
    await expect(emptyTrash).toBeEnabled();
    await emptyTrash.click();
    const dialog = page.getByTestId('confirm-dialog');
    await expect(dialog).toBeVisible();
    const n = trashed.items.length;
    await expect(dialog).toContainText(`Empty Trash? (${n} ${n === 1 ? 'event' : 'events'})`);
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect(deleteRequests).toBe(0);
    await expect(card).toBeVisible();

    // The card's own permanent-delete overlay also cancels clean: dialog
    // mounts (role=dialog inside the card), Cancel unmounts it, no DELETE.
    await card.getByRole('button', { name: 'Delete Forever', exact: true }).click();
    const cardConfirm = card.locator('[role="dialog"]');
    await expect(cardConfirm).toBeVisible();
    await cardConfirm.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(cardConfirm).toHaveCount(0);
    expect(deleteRequests).toBe(0);

    // "restores one": the card's Restore button POSTs the row's cited
    // /restore leg and the invalidated list drops the card.
    const atRestore = restorePosts.length;
    await card.getByRole('button', { name: 'Restore', exact: true }).click();
    await expect.poll(() => restorePosts.length).toBeGreaterThan(atRestore);
    expect(restorePosts[restorePosts.length - 1].status).toBe(200);
    await expect(card).toHaveCount(0);

    // "selects several and clicks Restore selected": Select All now marks the
    // remaining pair, the bulk bar mirrors the count, and the bulk handler
    // restores every selection (it fans mutateAsync over selectedIds).
    await page.getByTestId('select-all-button').click();
    const bar = page.getByTestId('bulk-action-bar');
    await expect(bar).toBeVisible();
    await expect(bar).toContainText(`${trashed.items.length - 1} events selected`);
    const atBulk = restorePosts.length;
    await page.getByTestId('restore-selected-button').click();
    await expect
      .poll(() => restorePosts.length - atBulk)
      .toBeGreaterThanOrEqual(trashed.items.length - 1);
    for (const p of restorePosts.slice(atBulk)) expect(p.status).toBe(200);

    // Trash is empty now: EmptyState, and the header button flips to disabled
    // (disabled={… || isEmpty}, TrashPage.tsx:358 — the coupling clause).
    await expect(page.getByText('Trash is empty')).toBeVisible();
    await expect(emptyTrash).toBeDisabled();

    // Backend truth after the UI's mutations: every seed is back in the
    // active list and the trash is empty at the source.
    const after = await api<DeletedListBody>(h, session, '/api/events/deleted');
    expect(after.items).toEqual([]);
    const active = await api<EventListBody>(h, session, '/api/events?limit=5');
    for (const id of seeds) expect(active.items.map((e) => e.id)).toContain(id);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
