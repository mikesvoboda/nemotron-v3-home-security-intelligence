/**
 * F-195 (inventory 3.9): Admin › Logging settings — a scoped partial of the
 * row. The inventory row (`docs/reference/feature-inventory.md:379`) carries
 * FOUR clauses; this spec executes THREE of them and names the one it does not:
 *   (a) "expands Logging Settings"      — openAdminSection + toBeVisible
 *   (b) "sees log file/DB config"        — NOT executed here (no assertion; the
 *       panel's file/DB readout has no CI-reachable witness, so it stays a gap
 *       for the row, not a claim)
 *   (c) "clicks a level button"          — the LOG_LEVELS buttons, backend-confirmed
 *   (d) "edits log retention days and saves" — executed, backend-confirmed, restored
 * Claiming all four, or a tidy "three", would over-state the row: (b) is why the
 * row is not fully witnessed by this file.
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
 * Clause (d) — "edits log retention days and saves" — used to be pinned
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

test.describe('golden path: admin logging level control and retention save (F-195) @critical', () => {
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
    // `found` is read from the SAME endpoint the panel loads from, and the slider
    // is then asserted to show it. Taking `inputValue()` as the source of truth
    // instead would let a panel still holding its `useState<number>(7)` seed pick
    // the number: the loader's `catch {}` (LoggingSettings.tsx:129-131) swallows a
    // failed config GET yet still clears the loading flag in `finally`, so the
    // card renders on the seed and the leg would restore 7 over a real 21 and go
    // green. Asserting the pair closes that, and `toHaveValue` retries — so it is
    // also the "slider has the loaded value" sync point, rather than a prose
    // promise about load order.
    const retention = page.getByTestId('log-retention-settings');
    await expect(retention).toBeVisible();
    const slider = retention.getByLabel('Log retention period in days');
    const found = Number(
      (await api<SystemConfigBody>(h, session, '/api/system/config')).log_retention_days
    );
    // Both ends, not just the floor. The direction arithmetic below assumes
    // `found` is INSIDE the slider's [1,90]; a value above max would make the
    // DOM clamp (native range inputs clamp `value` to [min,max] on render) while
    // `saved = found ± 1` keeps the raw number, so the leg would red on the
    // persistence assertion for a reason that has nothing to do with persistence.
    // The arm is API-reachable, not merely hypothetical: the PATCH request model
    // bounds this field ge=1/le=365 (backend/api/schemas/system.py:554-559,
    // ConfigUpdateRequest — measured by calling the model directly: 91/120/365
    // ACCEPT, 366/0/-5/500 reject), so 91..365 is a value the backend will store
    // and the slider cannot render. The 422 this leg first measured was for 500,
    // which is outside 365 — it proved the SCHEMA bound, not a clamp at 90, so
    // the earlier note here declared the arm dead on a probe that never tested
    // the window in question. Nothing in this repo PATCHes above 90, which makes
    // it reachable rather than current; nothing pins max="90" against le=365
    // either, so this guard is what keeps the two windows from diverging quietly.
    expect(found).toBeGreaterThanOrEqual(1); // backend field default 7; slider min 1
    expect(found).toBeLessThanOrEqual(90); // slider max; keeps `saved` DOM-representable
    await expect(slider).toHaveValue(String(found));
    // Step INWARD from whichever end the value sits at. At max=90 ArrowRight is
    // a native no-op, and a value that did not move leaves hasRetentionChanges
    // false — the Save button would stay disabled and the leg would fail for a
    // reason that has nothing to do with persistence. Both arms measured on a
    // CI-shape stack: found=90 saves 89, found=1 saves 2, so the save always
    // lands interior, Save always enables, and the restore key is never a no-op.
    const dir = found >= 90 ? 'ArrowLeft' : 'ArrowRight';
    const saved = found >= 90 ? found - 1 : found + 1;
    await slider.focus();
    await page.keyboard.press(dir); // native range input: +/-1 step (1 day)
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
    // spec a different retention. Same witness, same path. The key is the
    // INVERSE of the save's, which is why the save's direction is stored rather
    // than inlined: at found=90 the save stepped LEFT, so restoring LEFT again
    // would save 88 and the assertion below would be checking the wrong number.
    //
    // The waiter is installed BEFORE the click, and the read happens only after
    // the PATCH response resolves. Save #1 is synchronized by the toast, which
    // LoggingSettings.tsx:166 fires after updateConfig resolves; this second save
    // deliberately asserts no toast (see below), so without a wait of its own the
    // GET used to be fired while save #2's PATCH was still in flight. The route
    // clears the settings cache before it answers (system.py:2668, ahead of the
    // audit-log await at :2697), so the read was beating its own write: measured
    // red at attempt 1 at found=7/21/90/1 with `Received` always exactly `saved`,
    // and 29 of 30 immediate GETs read the pre-write value against 25 of 25
    // correct once awaited. CI hid it — CI=1 selects retries: 2
    // (playwright.config.ts:79) and failOnFlakyTests is unset, so attempt 2 went
    // green, the junit row carried no <failure> child, and junit_results()
    // (scripts/feature_check.py:853) called it `passed`. Under UR-129 a failed
    // attempt makes the spec `flaky` whatever its final outcome, and UR-128 says a
    // row flips only on a run whose test passed, so a retry-laundered green is not
    // a witness for this row no matter what the harness prints.
    const restoreSaved = page
      .waitForResponse(
        (response) =>
          response.request().method() === 'PATCH' &&
          new URL(response.url()).pathname === '/api/system/config',
        { timeout: 20_000 }
      )
      .catch(() => null);
    await slider.focus();
    await page.keyboard.press(dir === 'ArrowRight' ? 'ArrowLeft' : 'ArrowRight');
    await expect(retention.getByTestId('retention-save-button')).toBeEnabled();
    await retention.getByTestId('retention-save-button').click();
    const restoreResponse = await restoreSaved;
    expect(
      restoreResponse,
      'the restore save must reach the backend and be answered'
    ).not.toBeNull();
    // No toast assertion here: a success toast from save #1 may still be on
    // screen (sonner's own auto-dismiss decides when), so "a success toast is
    // visible" would pass even if this save failed and "two toasts" would
    // race that dismiss timer. The witness is the answered PATCH above plus this
    // read: patch_config clears the settings cache, so a value that did not reach
    // the runtime env would still answer the OLD number here.
    const back = await api<SystemConfigBody>(h, session, '/api/system/config');
    expect(back.log_retention_days).toBe(found);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
