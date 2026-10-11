/**
 * F-146 (inventory 3.8): WebSocket health — the event and system broadcaster
 * cards render with circuit state.
 *
 * GET /api/system/health/websocket first (both broadcasters reported Healthy
 * on the harness stack's DOM probe); the section then carries a card and a
 * status badge per broadcaster.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: websocket health @critical', () => {
  test.setTimeout(60_000);

  test('both broadcaster cards render with health badges', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const health = await api<Record<string, unknown>>(h, session, '/api/system/health/websocket');
    expect(Object.keys(health).length).toBeGreaterThan(0);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'websocket-health');
    await expect(page.getByTestId('websocket-health-panel')).toBeVisible();
    for (const which of ['event', 'system'] as const) {
      await expect(page.getByTestId(`broadcaster-card-${which}`)).toBeVisible();
      await expect(page.getByTestId(`broadcaster-status-badge-${which}`)).toBeVisible();
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
