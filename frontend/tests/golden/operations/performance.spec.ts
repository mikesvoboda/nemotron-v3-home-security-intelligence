/**
 * F-170 + F-172 (inventory 3.8): /performance real-time cards (GPU, AI models,
 * PostgreSQL, Redis, host, containers, connection badge) and the time-series
 * charts fed by client-side history of WS performance_update messages.
 *
 * Data-source note that shapes the waits: unlike the operations page (REST
 * polling), this page's cards and charts fill from the WEBSOCKET stream —
 * broadcast_performance on /ws/system every 5 s (system_broadcaster.py:1100),
 * with client-side history as the chart source (F-172's evidence cell). The
 * probe measured the first performance_update 173 ms after WS open, so
 * "Connected" is the gate everything below waits on; the guard's route
 * tripwire does not touch the real WS because nothing here intercepts it.
 *
 * The time-range buttons expose no aria-pressed state (PerformanceCharts.tsx
 * :330-344 signals the active range ONLY through the bg-[#76B900] class), so
 * the class IS the contract here — asserted with a comment at the call site.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, loginAsAdmin, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: performance page @critical', () => {
  test.setTimeout(90_000);

  test('metric cards render from the live websocket stream (F-170)', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await loginAsAdmin(page, h);

    await page.goto(`${h.ui}/performance`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('performance-dashboard')).toBeVisible();

    // The row's "connection badge": green dot + Connected once /ws/system is
    // open. Strict mode bites here (measured): the dashboard header carries
    // its own dot with data-testid="connection-indicator" title="Connected"
    // AND the charts header renders one too — so scope to the charts header,
    // which is the WS-status surface this page's row is about.
    const charts = page.getByTestId('performance-charts');
    await expect(charts.getByTestId('connection-indicator')).toBeVisible();
    await expect(charts.getByText('Connected', { exact: true })).toBeVisible({ timeout: 20_000 });

    // The row names the card set; yolo26/nemotron are the two ai-model slots.
    // These are CARD BODIES gated on WS data, not static chrome: AiModelsCard
    // renders "No AI model data available" until the aiModels record has an
    // entry (PerformanceDashboard.tsx:344-348), and every card here fills
    // from the first performance_update on /ws/system. Run 5 proved the 5 s
    // default expires when the socket opens late or a reconnect blips under
    // the rate limiter — same class as databases.spec.ts's card bodies. 30 s
    // covers open + first broadcast on a healthy stream (~1.5 s measured).
    for (const testId of [
      'gpu-card',
      'ai-model-yolo26',
      'ai-model-nemotron',
      'database-card',
      'redis-card',
      'host-card',
      'containers-card',
    ]) {
      await expect(page.getByTestId(testId)).toBeVisible({ timeout: 30_000 });
    }
    // Status badges (the "with a connection badge" leg per card family).
    await expect(page.getByTestId('db-status')).toBeVisible();
    await expect(page.getByTestId('ai-model-yolo26-status')).toBeVisible();
    await expect(page.getByTestId('ai-model-nemotron-status')).toBeVisible();

    // The 5m/15m/60m picker exists on this page (its behavior is F-172).
    for (const range of ['5m', '15m', '60m']) {
      await expect(page.getByTestId(`time-range-${range}`)).toBeVisible();
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('charts grow from streamed history and the range picker switches series (F-172)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    // This test waits out the 60m bucket's downsample floor (header), so it
    // needs more than the describe's 90s.
    test.setTimeout(150_000);
    const h = harness;
    await loginAsAdmin(page, h);

    await page.goto(`${h.ui}/performance`, { waitUntil: 'domcontentloaded' });
    const charts = page.getByTestId('performance-charts');
    await expect(charts.getByText('Connected', { exact: true })).toBeVisible({ timeout: 20_000 });

    // Charts flip from the empty-chart placeholder to real series as the
    // 5m buffer accumulates (hasGpuData/hasHostData/hasInferenceData gate
    // off the ACTIVE range's buffer, PerformanceCharts.tsx:273-275; the
    // default range is 5m, which takes EVERY update — usePerformanceMetrics
    // .ts:386-393). The 4th empty-chart is the inference card: the fake-ai
    // probe stack streams inference objects whose *_latency_ms.avg are all
    // 0 (measured raw WS body), and hasInferenceData accepts any defined
    // avg — 0 included — so it clears on the first update too.
    await expect(page.getByTestId('gpu-area-chart')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('temperature-line-chart')).toBeVisible();
    await expect(page.getByTestId('resource-area-chart')).toBeVisible();
    await expect(page.getByTestId('empty-chart')).toHaveCount(0);

    // Range switch: active is class-signalled only (header comment), so the
    // assertion reads the same class the component writes.
    const green = /bg-\[#76B900\]/;
    await expect(page.getByTestId('time-range-5m')).toHaveClass(green);
    await page.getByTestId('time-range-15m').click();
    await expect(page.getByTestId('time-range-15m')).toHaveClass(green);
    await expect(page.getByTestId('time-range-5m')).not.toHaveClass(green);
    // The range change re-slices against the 15m bucket, which fills only
    // every 3rd update (SAMPLING_RATES, usePerformanceMetrics.ts:396-403) —
    // at the measured ~5.1 s cadence its FIRST point lands ~15 s after mount.
    // Tests reaching this line ~2 s after load therefore face a legitimately
    // EMPTY 15m slice: the placeholders must render, and counting them to 0
    // with the 3 s default was run 5's failure — a spec timing bug I had
    // misattributed to run 3's WS starvation. The honest wait is the bucket
    // fill, same as the 60m leg below.
    await expect(page.getByTestId('empty-chart')).toHaveCount(0, { timeout: 30_000 });
    await expect(page.getByTestId('gpu-area-chart')).toBeVisible();
    await page.getByTestId('time-range-60m').click();
    await expect(page.getByTestId('time-range-60m')).toHaveClass(green);
    // 60m is the honest floor of this path, measured: the 60m buffer adds
    // only every 12th update and the stack broadcasts performance_update
    // every ~5.1 s (WS probe: 19 updates in 95 s), so the first 60m point
    // lands ~60 s after page load. Before then the 60m slice is empty and
    // the placeholders LEGITIMATELY render — run 2's "Received: 4" was the
    // spec checking too early, not a product break.
    await expect(page.getByTestId('empty-chart')).toHaveCount(0, { timeout: 75_000 });
    await expect(page.getByTestId('gpu-area-chart')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
