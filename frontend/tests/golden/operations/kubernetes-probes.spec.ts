/**
 * F-147 (inventory 3.8): Kubernetes liveness/readiness probe cards, polled
 * every 15 s.
 *
 * The probes the page shows are the backend's own /api/system/health/live and
 * /health/ready — asserted from Node first, then matched against the page's
 * per-probe badges. (This is also the row's own honesty check: the panel
 * renders what the probes actually answered, DOM-probed "All Passing".)
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: kubernetes probes @critical', () => {
  test.setTimeout(60_000);

  test('liveness and readiness cards pass, matching the real probe endpoints', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const live = await fetch(`${h.api}/api/system/health/live`, {
      headers: { Cookie: `${session.name}=${session.value}` },
    });
    const ready = await fetch(`${h.api}/api/system/health/ready`, {
      headers: { Cookie: `${session.name}=${session.value}` },
    });
    expect(live.status).toBe(200);
    expect(ready.status).toBe(200);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'kubernetes-probes');
    await expect(page.getByTestId('kubernetes-probes-panel')).toBeVisible();
    await expect(page.getByTestId('probe-card-liveness')).toBeVisible();
    await expect(page.getByTestId('probe-card-readiness')).toBeVisible();
    await expect(page.getByTestId('probe-status-badge-liveness')).toBeVisible();
    await expect(page.getByTestId('probe-status-badge-readiness')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
