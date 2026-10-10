/**
 * F1.2 (UR-18) — verdict-engine banner appears and clears in a real browser.
 *
 * Done-when clause: "the PR shows the banner appearing and clearing as ai-vlm
 * is stopped and started on a running stack." This spec covers the VISIBLE-UI
 * half of that clause in the browser, driven by the readiness field the panel
 * reads:
 *
 *   GET /api/system/health/ready -> verdict_engine {state, since, reason}
 *
 * B1.4 derives that field solely from an `ai-vlm` /health reachability probe,
 * so a stop/start of the service is expressed to the frontend as that field
 * flipping available -> unavailable -> available. This spec drives exactly
 * that flip through a mocked readiness response and asserts what the operator
 * would see on a running stack: the alarm banner appears, reads the elapsed
 * downtime, and clears on recovery.
 *
 * The compose-level stop/start on the test deployment remains the owner-tier
 * run (operator.md keeps deployment control); this spec is the half the PR
 * can demonstrate itself.
 *
 * The readiness route is registered AFTER the fixture's auto-mock on purpose:
 * Playwright matches routes in reverse registration order, so this handler
 * wins for /api/system/health/ready while the fixture still serves everything
 * else the app needs to boot.
 */
import { expect } from '@playwright/test';

import { test } from '../fixtures';

/** Transition time pinned so elapsed formatting is deterministic. */
const SINCE = '2026-10-08T10:00:00Z';

function readinessBody(state: 'available' | 'unavailable') {
  return {
    ready: true,
    workers: [
      { name: 'file-watcher', running: true, critical: true, message: 'Watching' },
      { name: 'batch-aggregator', running: true, critical: true, message: 'Processing' },
    ],
    timestamp: new Date().toISOString(),
    verdict_engine: {
      state,
      since: state === 'unavailable' ? SINCE : null,
      reason: state === 'unavailable' ? 'ai-vlm service connection refused' : null,
    },
  };
}

test.describe('verdict-engine banner (F1.2)', () => {
  // Headroom for dev-server cold start only (ruling 52). The two poll
  // convergences are no longer real waits: the page runs on Playwright's fake
  // clock, so each one is advanced past one 15 s interval in milliseconds.
  test.setTimeout(30_000);

  test('banner appears when the engine goes down and clears when it recovers', async ({ page }) => {
    let engineState: 'available' | 'unavailable' = 'available';

    await page.route('**/api/system/health/ready', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(readinessBody(engineState)),
      });
    });

    // Auth gate: the fixture mocks no auth endpoints, so ProtectedRoute would
    // redirect to /login and the banner (rendered by Layout, inside a
    // protected route) would never mount. Two canned responses get past it —
    // setup not required, and a signed-in user.
    await page.route('**/api/auth/setup-status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ setup_required: false }),
      });
    });
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          username: 'e2e',
          email: 'e2e@example.com',
          is_active: true,
          is_admin: true,
          created_at: '2026-01-01T00:00:00Z',
          last_login_at: null,
        }),
      });
    });

    // Ruling 52: run on Playwright's fake clock. The hook's only page-side
    // timer is the 15 s readiness setInterval (useVerdictEngineStatus.ts:202);
    // the fetch itself is fulfilled by page.route() in the Node process, which
    // the fake clock does not touch, so one fastForward() past the interval
    // replaces each former multi-second real wait (fastForward fires the due
    // poll once — the lid-closed semantics — instead of stepping through the
    // window's unrelated 1 s timers as runFor would). The timeouts below stay
    // as safety caps; they are no longer the mechanism that makes this pass.
    await page.clock.install();

    await page.goto('/');

    const banner = page.getByTestId('verdict-engine-banner');

    // 1. Healthy boot: no banner. This is the first-paint regression guard in
    //    the browser — an ungated render would flash "state unknown" here.
    await expect(banner).toHaveCount(0);

    // 2. Engine goes down (the `docker compose stop ai-vlm` equivalent). The
    //    banner arrives on the next readiness poll, so jump one interval over.
    engineState = 'unavailable';
    await page.clock.fastForward(16_000);
    await expect(banner).toBeVisible({ timeout: 25_000 });
    await expect(banner).toContainText(/verdict engine unavailable/i);
    await expect(banner).toContainText(/need.{0,20}review/i);
    await expect(page.getByTestId('verdict-engine-since')).toContainText(/unavailable for/);
    await expect(page.getByTestId('verdict-engine-reason')).toContainText(/connection refused/i);

    // 3. Engine comes back (the `start ai-vlm` equivalent): the banner clears
    //    on the next poll — again one fake interval, not a real 15 s wait.
    engineState = 'available';
    await page.clock.fastForward(16_000);
    await expect(banner).toHaveCount(0, { timeout: 25_000 });
  });
});
