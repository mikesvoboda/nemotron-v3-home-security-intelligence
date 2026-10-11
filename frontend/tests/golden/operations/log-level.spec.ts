/**
 * F-159 (inventory 3.8): the log level control shows the current root level
 * and clicking another level changes it.
 *
 * The level is PROCESS state, not page state — an earlier probe found its own
 * WARNING leftover still in force after every process around it had moved on.
 * So this spec reads the current level from the endpoint, clicks a DIFFERENT
 * level (WARNING when the current is INFO, else INFO), asserts both the panel
 * and the backend agree, then RESTORES the original through the UI path it
 * just proved — a green run must not hand the next spec a noisier root logger.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from './harness';

const harness = readOpsHarness();

interface LogLevelBody {
  level?: string;
  current_level?: string;
}

function levelOf(body: LogLevelBody): string {
  return String(body.level ?? body.current_level ?? '');
}

test.describe('golden path: log level control @critical', () => {
  test.setTimeout(60_000);

  test('clicking a level changes the root logger, and the original is restored', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const before = levelOf(await api<LogLevelBody>(h, session, '/api/debug/log-level'));
    expect(before).toMatch(/^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$/);
    const target = before === 'WARNING' ? 'INFO' : 'WARNING';

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'log-level');
    const section = page.getByTestId('log-level-section');
    await expect(section).toContainText(new RegExp(`Current Level:\\s*${before}`));

    await page.locator('button', { hasText: new RegExp(`^${target}$`) }).first().click();
    await expect(section).toContainText(new RegExp(`Current Level:\\s*${target}`), {
      timeout: 10_000,
    });
    // The backend agrees — this is root-logger state, not a label repaint.
    const after = levelOf(await api<LogLevelBody>(h, session, '/api/debug/log-level'));
    expect(after).toBe(target);

    // Restore through the same control; leave no side effect for other specs.
    await page.locator('button', { hasText: new RegExp(`^${before}$`) }).first().click();
    await expect(section).toContainText(new RegExp(`Current Level:\\s*${before}`), {
      timeout: 10_000,
    });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
