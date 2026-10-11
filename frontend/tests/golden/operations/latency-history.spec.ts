/**
 * F-150 (inventory 3.8): per-stage p50/p95/p99 pipeline latency over the last
 * hour.
 *
 * The data precondition is load-bearing, measured on the harness stack:
 * GET /api/system/pipeline-latency/history (window_minutes=60, 60 s buckets)
 * answers snapshots: [] on a fresh stack, and the panel's EMPTY branch
 * renders no view toggle at all (PipelineLatencyHistoryPanel.tsx:216 renders
 * the toggle only in the data branch, :121) — run 3 failed here because the
 * precondition accepted Array.isArray([]) as truth. So this spec seeds when
 * empty, through the same endpoint the TestData panel's own mutation calls
 * (POST /api/admin/seed/pipeline-latency, useAdminMutations.ts:252).
 *
 * The seed's own arithmetic matters: samples backdate evenly across
 * time_span_hours (admin.py:959-984), and the panel reads the LAST 60
 * MINUTES only. The UI's 7-day default (168 h) measured 0 snapshots — 100
 * samples over 168 h put at most one inside the window, often none. The
 * precondition seed therefore uses time_span_hours: 1 (measured: 60
 * snapshots, p50/p95/p99 populated). The UI click below keeps its own
 * default 7, which seeds the tracker (200 + toast) but can leave the
 * 60-minute window thin — the panel asserts below only what the precondition
 * guarantees, and the thin-window default is evidence on the F-161 row, not
 * an assertion here.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  authPostOk,
  closedByGuard,
  loginAsAdmin,
  openSection,
  panelRecovers,
  pollApi,
  readOpsHarness,
} from './harness';

const harness = readOpsHarness();

test.describe('golden path: pipeline latency history @critical', () => {
  test.setTimeout(60_000);

  test('stage chart renders and the Percentiles view toggles', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    let body = await api<{ snapshots?: unknown[]; window_minutes?: number }>(
      h,
      session,
      '/api/system/pipeline-latency/history',
    );
    if ((body.snapshots?.length ?? 0) === 0) {
      await authPostOk(h, session, '/api/admin/seed/pipeline-latency', {
        time_span_hours: 1,
        num_samples: 100,
      });
      body = await pollApi<{ snapshots?: unknown[] }>(
        h,
        session,
        '/api/system/pipeline-latency/history',
        (b) => (b.snapshots?.length ?? 0) > 0,
        20_000,
      );
    }
    expect((body.snapshots?.length ?? 0) > 0).toBe(true);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'latency-history');
    const card = page.getByTestId('pipeline-latency');
    await expect(card).toBeVisible();
    // The panel fetched, its request failed at the stalled redis middleware
    // (measured run 5: error branch on screen while my Node-side read of the
    // same endpoint had passed seconds before) — and it REUSES the root
    // testid in its error branch, so the error locator stays scoped inside
    // the card. Driving the panel's own Retry (harness panelRecovers) keeps
    // the golden path honest: the page ships recovery, the spec uses it.
    await panelRecovers(
      card,
      card.getByTestId('pipeline-latency-error'),
      card.getByTestId('pipeline-latency-loading'),
    );

    // Percentiles view is the row's p50/p95/p99 surface; the toggle must
    // actually switch the pressed state.
    await expect(page.getByTestId('pipeline-latency-view-percentiles')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await page.getByTestId('pipeline-latency-view-percentiles').click();
    await expect(page.getByTestId('pipeline-latency-view-percentiles')).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
