/**
 * F-195 (inventory 3.9): Admin › Logging settings — a scoped partial of the
 * row, with its retention-save leg cited for demotion.
 *
 * LoggingSettings is the only AdminSettings section whose reads work on the
 * CI stack: its legs are GET /api/debug/config, the log-level GET/POST pair,
 * and GET /api/system/config (LoggingSettings.tsx:86-127) — all live
 * (measured 200 here and in OP-1's operations/log-level.spec.ts). This spec
 * proves the row's "clicks a level button" clause through the panel's OWN
 * controls, with the restore discipline F-159's spec established: the level
 * is process-global root-logger state, so a green run must leave it exactly
 * where it found it, and it asserts the BACKEND agrees, not just the label.
 *
 * The row's last clause — "edits log retention days and saves" — cannot pass
 * on the CI compose: the save PUTs PATCH /api/system/config
 * (LoggingSettings.tsx:164 → services/api.ts:2102), and the backend cannot
 * persist any config write there — backend has read_only: true
 * (docker-compose.ci.yml:103) and the route writes ./data/runtime.env,
 * measured answering 500 "[Errno 30] Read-only file system: 'runtime.env'"
 * (backend/api/routes/system.py patch_config :2590; F-190/F-191's PATCH
 * /api/v1/settings dies the same way via settings_api.py:159). The spec ends
 * on that edge deliberately: it EDITS the retention slider (so the Save
 * button enables — proof the edit path works) and asserts the save FAILS with
 * the product's own toast, pinning the break instead of skipping it. When the
 * persistence class is fixed the toast flips to "Log retention updated" and
 * this assertion fails loudly, pointing right here.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';
import { openAdminSection } from './harness';

const harness = readOpsHarness();

interface LogLevelBody {
  level?: string;
  current_level?: string;
}

function levelOf(body: LogLevelBody): string {
  return String(body.level ?? body.current_level ?? '');
}

test.describe('golden path: admin logging level control and retention-save break @critical', () => {
  test.setTimeout(90_000);

  test('the level buttons change and restore the root logger, and the retention save pins the read-only-fs break', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const before = levelOf(await api<LogLevelBody>(h, session, '/api/debug/log-level'));
    expect(before).toMatch(/^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$/);
    const target = before === 'WARNING' ? 'INFO' : 'WARNING';

    await page.goto(`${h.ui}/settings/admin`, { waitUntil: 'domcontentloaded' });
    await openAdminSection(page, 'admin-logging-settings', 'logging-settings');
    const card = page.getByTestId('logging-settings');
    await expect(card).toBeVisible();
    await expect(card).toContainText(new RegExp(`Current Level:\\s*${before}`));

    // Row clause "clicks a level button": the panel's own LOG_LEVELS buttons
    // (:266-284), then the backend confirms — root-logger state, not a label
    // repaint. (Same contract F-159's operations spec proved on ITS host.)
    await card.getByRole('button', { name: target, exact: true }).click();
    await expect(card).toContainText(new RegExp(`Current Level:\\s*${target}`), {
      timeout: 10_000,
    });
    const after = levelOf(await api<LogLevelBody>(h, session, '/api/debug/log-level'));
    expect(after).toBe(target);

    // Restore through the same control; leave no side effect for other specs.
    await card.getByRole('button', { name: before, exact: true }).click();
    await expect(card).toContainText(new RegExp(`Current Level:\\s*${before}`), {
      timeout: 10_000,
    });

    // Row clause "edits log retention days and saves" — the pinned break.
    const retention = page.getByTestId('log-retention-settings');
    await expect(retention).toBeVisible();
    const slider = retention.getByLabel('Log retention period in days');
    await slider.focus();
    await page.keyboard.press('ArrowRight'); // native range input: +1 step (1 day)
    await expect(retention.getByTestId('retention-save-button')).toBeEnabled();
    await retention.getByTestId('retention-save-button').click();

    const toast = page.locator('[data-sonner-toast]').filter({
      hasText: 'Failed to update log retention',
    });
    await expect(toast).toBeVisible({ timeout: 15_000 });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
