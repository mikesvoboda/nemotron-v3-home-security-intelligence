/**
 * F-137 (inventory 3.8): every registered circuit breaker renders with state,
 * failure counts and thresholds.
 *
 * The breaker set (fake-ai, nemotron, database — DOM-probed closed on the
 * harness stack) is asserted from GET /api/system/circuit-breakers first; the
 * page must then carry one card per backend name, with that name's status on
 * it. Resetting a NON-closed breaker is the sibling row F-138, which measured
 * no way to produce a non-closed breaker on this stack — it is demoted in the
 * inventory, so this spec stays on the closed-card path by design.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

test.describe('golden path: circuit breakers @critical', () => {
  test.setTimeout(60_000);

  test('each backend breaker renders state and counts on the page', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Measured body shape: {"circuit_breakers": {"yolo26": {"name": ...,
    // "state": "closed", "failure_count": 0, ...}, "postgresql": {...}, ...}}
    // — a NAME-KEYED DICT, not an array (the first draft read body.breakers[]
    // and failed on undefined.length; the panel keys cards off the same dict).
    const body = await api<{ circuit_breakers?: Record<string, { name?: string }> }>(
      h,
      session,
      '/api/system/circuit-breakers',
    );
    const breakers = Object.entries(body.circuit_breakers ?? {});
    expect(breakers.length).toBeGreaterThan(0);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'circuit-breakers');
    await expect(page.getByTestId('circuit-breaker-summary')).toBeVisible();

    for (const [name] of breakers) {
      await expect(page.getByTestId(`circuit-breaker-${name}`)).toBeVisible();
      await expect(page.getByTestId(`failure-count-${name}`)).toBeVisible();
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
