/**
 * F-132 (inventory 3.8): /operations opens — header, Grafana banner with an
 * Open Grafana link, over a live telemetry/config read.
 *
 * The row also lists "a loading/error state with Retry for the telemetry
 * fetch"; that error branch is a branch, not the golden path, and forcing it
 * unmocked would mean breaking the stack to watch the page cope — guard.ts
 * forbids the mock and no endpoint toggles it. The header/banner/live-render
 * legs are the path; they were DOM-probed on the harness stack before this was
 * written (root testid operations-page, h1 Operations, banner + grafana-link).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: operations page opens @critical', () => {
  test.setTimeout(60_000);

  test('the header, the Grafana banner, and a live telemetry read render together', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Backend state before UI: the banner's own source (grafana_url) plus the
    // telemetry fetch the page lives on. An endpoint that 500s here would
    // otherwise only prove the page renders something.
    const config = await api<{ grafana_url?: string }>(h, session, '/api/system/config');
    expect(typeof config.grafana_url).toBe('string');
    const telemetry = await api<{ queues?: Record<string, number> }>(
      h,
      session,
      '/api/system/telemetry',
    );
    expect(telemetry.queues).toBeTruthy();

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('operations-page')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Operations', exact: true })).toBeVisible();
    await expect(page.getByTestId('grafana-monitoring-banner')).toBeVisible();
    await expect(page.getByTestId('grafana-link')).toBeVisible();
    await expect(page.getByTestId('pipeline-flow-visualization')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
