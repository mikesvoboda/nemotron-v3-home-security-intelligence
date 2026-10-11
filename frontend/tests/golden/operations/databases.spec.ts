/**
 * F-145 (inventory 3.8): PostgreSQL + Redis metric cards, and the Redis INFO
 * debug block that debug mode unhides.
 *
 * The debug block is gated on the frontend's OWN localStorage flag
 * (`system-debug-mode`, DatabasesPanel's debugMode prop) — not the backend
 * DEBUG env — so a golden spec seeds it through addInitScript, the same
 * mechanism guard.ts itself uses for the tour keys: it is state a real
 * visiting admin produced once and the browser remembers, not traffic
 * interception. (The toggle that flips that flag on demand is F-133, a
 * separate row, demoted: DebugModeToggle renders only when the backend says
 * debug=true and docker-compose.ci.yml:131 pins DEBUG=false.)
 *
 * /api/debug/* is live on the harness stack despite that DEBUG=false —
 * require_debug_mode (backend/api/routes/debug.py:57) is a `pass` stub — which
 * is exactly why the endpoint leg is asserted from Node before the UI: the
 * block must render the real redis_version the endpoint carries.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: databases + redis debug block @critical', () => {
  test.setTimeout(60_000);

  test('postgres/redis cards render, and seeded debug mode reveals Redis INFO', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // The debug block's data source, asserted before the browser even
    // navigates: a real version string, reachable with the admin cookie.
    const debug = await api<{ info?: { redis_version?: string } }>(
      h,
      session,
      '/api/debug/redis/info',
    );
    expect(typeof debug.info?.redis_version).toBe('string');

    await page.addInitScript(() => {
      try {
        localStorage.setItem('system-debug-mode', 'true');
      } catch {
        /* storage may be unavailable; the block then stays hidden and asserts fail loudly */
      }
    });

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'databases');

    // Card HEADERS render always; the card BODIES — the metric testids below —
    // render only once the WS-derived metrics exist: the page passes
    // performanceData?.databases?.postgresql down (SystemMonitoringPage.tsx
    // :128-134) and DatabasesPanel.tsx:243 branches `postgresql ?` on it.
    // That data comes from the first performance_update on /ws/system
    // (~1.5 s on a healthy broadcaster; the 30 s budget is for CI where the
    // socket opens slower — run 3's 5 s default expired while the backend's
    // broadcaster loop was wedged, an environment failure, not a spec one).
    await expect(page.getByTestId('postgresql-card')).toBeVisible();
    await expect(page.getByTestId('redis-card')).toBeVisible();
    await expect(page.getByTestId('postgresql-connections')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('redis-memory')).toBeVisible({ timeout: 30_000 });

    // Debug leg: the seeded flag lights the block, and it carries the real
    // redis_version the Node leg just measured.
    const block = page.getByTestId('redis-debug-section');
    await expect(block).toBeVisible();
    await expect(block).toContainText(String(debug.info?.redis_version));

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
