/**
 * F-175 (inventory 3.8): /audit — stats cards, click-to-filter, the infinite
 * table, and an entry's detail modal.
 *
 * Data precondition (measured, with its trap): audit rows come from
 * production writers — every admin seed/clear action calls log_action — but
 * GET /api/audit DOCUMENTS pagination.total == 0 unless
 * include_total_count=true (backend/api/routes/audit.py:53-57, the NEM-2601
 * cursor-pagination optimization). A precondition asserting `total` would
 * fail on a database full of rows. So everything here counts items[], and the
 * seeding fallback posts the very endpoint the page itself audits
 * (POST /api/admin/seed/cameras — non-destructive, clear_existing defaults
 * False), then polls until the row appears.
 *
 * Row anatomy (AuditTableInfinite.tsx): the <tr> opens the detail modal, but
 * the Actor and Action cells are filter buttons that stopPropagation — so the
 * detail leg clicks the TIMESTAMP cell (col 1), which has no handler of its
 * own and bubbles to the row.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, authPost, closedByGuard, loginAsAdmin, pollApi, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: audit log @critical', () => {
  test.setTimeout(90_000);

  test('stats cards, action filter round trip, infinite scroll, detail modal', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Precondition: at least one row exists (see header on items vs total).
    let body = await api<{ items?: unknown[] }>(h, session, '/api/audit?limit=1');
    if ((body.items?.length ?? 0) === 0) {
      await authPost(h, session, '/api/admin/seed/cameras', { count: 1 });
      body = await pollApi<{ items?: unknown[] }>(
        h,
        session,
        '/api/audit?limit=1',
        (b) => (b.items?.length ?? 0) > 0,
        15_000,
      );
    }
    expect((body.items?.length ?? 0) > 0).toBe(true);

    await page.goto(`${h.ui}/audit`, { waitUntil: 'domcontentloaded' });

    // Stats cards (GET /api/audit/stats → four labeled cards + the by-action
    // breakdown; measured fresh stack: total 15 / today 15 / success 15).
    await expect(page.getByText('Total Audit Entries')).toBeVisible();
    await expect(page.getByText('Entries Today')).toBeVisible();
    await expect(page.getByText('Successful Operations')).toBeVisible();
    await expect(page.getByText('Actions by Type')).toBeVisible();

    // Filter leg: click an action badge (the stats-card badges carry
    // aria-pressed, AuditStatsCards.tsx:172) → chip appears → clear it →
    // table still standing. Use the table badge form so the assertion covers
    // the row control too.
    const actionBadge = page.getByRole('button', { name: /^Filter by action: / }).first();
    await expect(actionBadge).toBeVisible();
    await actionBadge.click();
    await expect(page.getByText('Active filters:')).toBeVisible();
    const chip = page.getByRole('button', { name: /^Clear action filter: / }).first();
    await expect(chip).toBeVisible();
    await chip.click();
    await expect(page.getByText('Active filters:')).toHaveCount(0);

    // Infinite-scroll leg: the sentinel renders only when a next page exists
    // (AuditLogPage.tsx:361 hasNextPage gate). On a small dev DB the first
    // page covers everything and the sentinel legitimately does not render —
    // when it DOES render, scroll it and require the table to grow or the
    // sentinel to vanish (end reached).
    const sentinel = page.getByTestId('infinite-scroll-sentinel');
    const rows = page.locator('tbody tr');
    await expect(rows.first()).toBeVisible();
    const before = await rows.count();
    if (await sentinel.isVisible().catch(() => false)) {
      await sentinel.scrollIntoViewIfNeeded();
      await expect
        .poll(
          async () =>
            (await rows.count()) > before || !(await sentinel.isVisible().catch(() => false)),
          { timeout: 15_000 },
        )
        .toBe(true);
    }

    // Detail-modal leg: click the timestamp cell (col 1 — no own handler, so
    // the click bubbles to the row; actor/action cells stopPropagation).
    // The role=dialog element CANNOT be toBeVisible here (measured):
    // <Dialog as="div"> puts role=dialog on the outer relative z-50 wrapper
    // (AuditDetailModal.tsx:102) whose only children are position:fixed
    // boxes (:113, :117) — the wrapper's own layout box is zero-height, so
    // Playwright scores it "hidden" even with data-open and the panel fully
    // on screen. Anchor instead on the wrapper's text (its subtree is the
    // modal content) and on the Close button, which is real and clickable.
    await rows.first().locator('td').first().click();
    const modalText = page.getByText('Entry Details');
    await expect(modalText).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Audit ID')).toBeVisible();
    const closeButton = page.getByRole('button', { name: 'Close modal' }).first();
    await expect(closeButton).toBeVisible();
    await closeButton.click();
    await expect(modalText).toHaveCount(0, { timeout: 10_000 });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
