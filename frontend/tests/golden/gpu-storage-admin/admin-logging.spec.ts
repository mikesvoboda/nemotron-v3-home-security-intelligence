/**
 * F-195 (inventory 3.9): Admin › Logging settings — a scoped partial of the
 * row, now covering ALL THREE of its clauses.
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
 * The third clause — "edits log retention days and saves" — used to be pinned
 * as a break here, because the save's PATCH /api/system/config
 * (LoggingSettings.tsx:164 → services/api.ts:2102) writes the runtime-override
 * env file and the backend could not write ANY file under read_only: true:
 * the route's default ./data/runtime.env answered 500
 * "[Errno 30] Read-only file system" (backend/api/routes/system.py
 * _runtime_env_path/_write_runtime_env). Ruling 127 routed that to F2.3 as
 * "`HSI_RUNTIME_ENV_PATH` (ops-b owns it)", and this batch ships it:
 * docker-compose.ci.yml's backend now sets HSI_RUNTIME_ENV_PATH=/tmp/runtime.env
 * onto a /tmp that was already a tmpfs there. So the clause is no longer
 * pinned-red — it is executed: the save must answer with the product's OWN
 * success toast, and the spec then re-reads GET /api/system/config and
 * asserts the BACKEND holds the new value, which is the part a toast cannot
 * show (a toast proves the fetch resolved; only the read proves the file
 * landed and the settings cache was cleared). Both saves restore through the
 * same control, because unlike the log level this one persists for the
 * container's life: a green run must leave the retention it found.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';
import { openAdminSection } from './harness';

const harness = readOpsHarness();

interface LogLevelBody {
  level?: string;
  current_level?: string;
}

interface SystemConfigBody {
  log_retention_days?: number;
}

function levelOf(body: LogLevelBody): string {
  return String(body.level ?? body.current_level ?? '');
}

test.describe('golden path: admin logging level control and retention save @critical', () => {
  test.setTimeout(90_000);

  test('the level buttons change and restore the root logger, and the retention save round-trips to the backend', async ({
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

    // Row clause "edits log retention days and saves" — executed, not pinned.
    // Read the value the panel loaded first: the restore and the backend
    // witness both key off it, and the row's Done-when is the round trip.
    const retention = page.getByTestId('log-retention-settings');
    await expect(retention).toBeVisible();
    const slider = retention.getByLabel('Log retention period in days');
    const found = Number(await slider.inputValue());
    expect(found).toBeGreaterThanOrEqual(1); // slider min=1, max=90
    await slider.focus();
    await page.keyboard.press('ArrowRight'); // native range input: +1 step (1 day)
    const saved = found + 1;
    await expect(retention.getByTestId('retention-save-button')).toBeEnabled();
    await retention.getByTestId('retention-save-button').click();

    // The save must answer with the product's OWN success string — the exact
    // toast this spec used to assert the opposite of. Matching on the success
    // text rather than "no error toast" is what makes the leg non-vacuous:
    // LoggingSettings.tsx:166 fires it only after updateConfig resolves.
    const ok = page.locator('[data-sonner-toast]').filter({
      hasText: 'Log retention updated',
    });
    await expect(ok).toBeVisible({ timeout: 15_000 });

    // The half the toast cannot show: the backend itself must hold the value.
    // patch_config clears the settings cache after writing the runtime env
    // (system.py), so a value that only reached the browser fails here.
    const cfg = await api<SystemConfigBody>(h, session, '/api/system/config');
    expect(cfg.log_retention_days).toBe(saved);

    // Restore through the same control: this save PERSISTS for the container's
    // life (unlike the log level), so leaving it changed would hand the next
    // spec a different retention. Same witness, same path.
    await slider.focus();
    await page.keyboard.press('ArrowLeft');
    await expect(retention.getByTestId('retention-save-button')).toBeEnabled();
    await retention.getByTestId('retention-save-button').click();
    // No toast assertion here: a success toast from save #1 may still be on
    // screen (sonner's own auto-dismiss decides when), so "a success toast is
    // visible" would pass even if this save failed and "two toasts" would
    // race that dismiss timer. The restore's witness is the backend read:
    // patch_config clears the settings cache, so a value that did not reach
    // the runtime env would still answer the OLD number here.
    const back = await api<SystemConfigBody>(h, session, '/api/system/config');
    expect(back.log_retention_days).toBe(found);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
