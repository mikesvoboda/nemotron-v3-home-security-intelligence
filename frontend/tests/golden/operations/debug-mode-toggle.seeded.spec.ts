/**
 * F-133 (inventory 3.8, seeded golden project — rulings 127, 187):
 * Operations › Debug mode toggle on `/operations` when the backend boots with
 * `DEBUG=true`.
 *
 * Flipping the switch writes `localStorage['system-debug-mode'] = 'true'`,
 * unhides the Redis INFO debug block (`redis-debug-section`) in the Databases
 * section on `/operations`, and unhides the `Raw Settings`
 * (`admin-raw-settings`) and `Developer Tools` (`admin-developer-tools`)
 * sections on `/settings/admin`.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from '../harness';

const harness = readOpsHarness();

interface SystemConfigBody {
  debug?: boolean;
}

test.describe('seeded golden path: operations debug mode toggle (F-133) @critical', () => {
  test.setTimeout(90_000);

  test('flips system-debug-mode on DEBUG=true backend and unhides Databases Redis INFO and Admin debug sections', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    test.info().annotations.push({
      type: 'seeded-branch',
      description: 'F-133 debug=true full toggle + Databases Redis INFO + Admin debug sections',
    });

    const cfg = await api<SystemConfigBody>(h, session, '/api/system/config');
    expect(cfg.debug).toBe(true);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('operations-page')).toBeVisible();

    const toggleRoot = page.getByTestId('debug-mode-toggle');
    await expect(toggleRoot).toBeVisible();
    const switchBtn = toggleRoot.getByRole('switch', { name: 'Toggle debug mode' });
    await expect(switchBtn).toBeVisible();
    await expect(switchBtn).toHaveAttribute('aria-checked', 'false');

    await openSection(page, 'databases');
    await expect(page.getByTestId('postgresql-card')).toBeVisible();
    await expect(page.getByTestId('redis-card')).toBeVisible();
    await expect(page.getByTestId('redis-debug-section')).toHaveCount(0);

    // Flip debug mode ON.
    await switchBtn.click();
    await expect(switchBtn).toHaveAttribute('aria-checked', 'true');
    const storedOn = await page.evaluate(() => localStorage.getItem('system-debug-mode'));
    expect(storedOn).toBe('true');
    await expect(page.getByTestId('redis-debug-section')).toBeVisible();

    // Verify /settings/admin Raw Settings and Developer Tools sections unhide.
    await page.goto(`${h.ui}/settings/admin`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('admin-raw-settings')).toBeVisible();
    await expect(page.getByTestId('admin-developer-tools')).toBeVisible();

    // Return to /operations and flip debug mode back OFF.
    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'databases');
    const switchBtnAfter = page
      .getByTestId('debug-mode-toggle')
      .getByRole('switch', { name: 'Toggle debug mode' });
    await expect(switchBtnAfter).toHaveAttribute('aria-checked', 'true');
    await switchBtnAfter.click();
    await expect(switchBtnAfter).toHaveAttribute('aria-checked', 'false');
    const storedOff = await page.evaluate(() => localStorage.getItem('system-debug-mode'));
    expect(storedOff).toBe('false');
    await expect(page.getByTestId('redis-debug-section')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
