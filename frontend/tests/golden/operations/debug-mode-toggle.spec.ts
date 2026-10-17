/**
 * F-133 (inventory 3.8): Operations › Debug mode toggle on `/operations`.
 *
 * `DebugModeToggle` (`frontend/src/components/system/DebugModeToggle.tsx:58-59`)
 * renders only when `GET /api/system/config` reports `debug: true`. On the
 * default CI stack (`docker-compose.ci.yml:131`, `DEBUG=false`), the component
 * returns `null` even if `localStorage['system-debug-mode']` is set; under the
 * ruling-127 `DEBUG=true` golden seed, the toggle mounts, writes
 * `localStorage['system-debug-mode']`, and unhides the Redis INFO debug block
 * in Databases (`redis-debug-section`).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from '../harness';

const harness = readOpsHarness();

interface SystemConfigBody {
  debug?: boolean;
}

test.describe('golden path: operations debug mode toggle (F-133) @critical', () => {
  test.setTimeout(60_000);

  test('mounts and flips system-debug-mode when backend debug=true, or stays hidden when debug=false', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const cfg = await api<SystemConfigBody>(h, session, '/api/system/config');
    expect(typeof cfg.debug).toBe('boolean');

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('operations-page')).toBeVisible();

    const toggleRoot = page.getByTestId('debug-mode-toggle');

    if (cfg.debug) {
      await expect(toggleRoot).toBeVisible();
      const switchBtn = toggleRoot.getByRole('switch', { name: 'Toggle debug mode' });
      await expect(switchBtn).toBeVisible();

      await openSection(page, 'databases');
      await expect(page.getByTestId('redis-debug-section')).toHaveCount(0);

      await switchBtn.click();
      await expect(switchBtn).toHaveAttribute('aria-checked', 'true');
      const storedOn = await page.evaluate(() => localStorage.getItem('system-debug-mode'));
      expect(storedOn).toBe('true');
      await expect(page.getByTestId('redis-debug-section')).toBeVisible();

      await switchBtn.click();
      await expect(switchBtn).toHaveAttribute('aria-checked', 'false');
      const storedOff = await page.evaluate(() => localStorage.getItem('system-debug-mode'));
      expect(storedOff).toBe('false');
      await expect(page.getByTestId('redis-debug-section')).toHaveCount(0);
    } else {
      // With DEBUG=false on the backend, DebugModeToggle returns null (:58-59).
      await expect(toggleRoot).toHaveCount(0);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
