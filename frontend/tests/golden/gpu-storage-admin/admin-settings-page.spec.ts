/**
 * F-187 (inventory 3.9): the Admin Settings page at /settings/admin — a
 * scoped partial of the row, with its load-from-API clause re-pinned after the
 * fix landed.
 *
 * The row's core clause is "sections load from the settings API". That clause
 * WAS dead on every stack the app shipped, and the account is kept here
 * because the tripwire below is what proved it: GET /api/v1/settings answered
 * 500 because settings_api.py fed settings.fast_path_confidence_threshold
 * (default 2.0, `le=10.0`, under the deliberate "DISABLED — set to impossible
 * value (>1.0)" note) into DetectionSettings.fast_path_threshold, whose schema
 * caps it at le=1.0 — pydantic rejected its own default and the route never
 * returned. Owner ruling 168 (option b) removed the out-of-band sentinel: the
 * disabled state is now the explicit `fast_path_enabled` bool (default false),
 * and the threshold is restricted to 0-1.0 where it always claimed to live.
 * The route therefore answers 200 and the page renders from the API, so this
 * spec now pins the loaded page. The fallback render it used to pin is still
 * real code (AdminSettings.tsx falls back to DEFAULT_FEATURE_TOGGLES when
 * settings is undefined) but it is no longer the path this page is on.
 *
 * The row's debug-mode parenthetical is still pinned false here: Raw Settings
 * and Developer Tools mount only under debugMode (:787, :805), and
 * DebugModeContext forces debugMode false whenever the backend reports
 * debug=false ("When isDebugAvailable is false, debugMode will always be
 * false regardless of localStorage", DebugModeContext.tsx:10-11) — the CI
 * compose pins DEBUG=false (docker-compose.ci.yml:131). The F-196/F-197
 * demotions cite the same gate.
 *
 * The spec also counts the six toggle switches, because the row's
 * "6/6 enabled" section summary is an arithmetic on FEATURE_TOGGLE_CONFIGS
 * (:84) and the six `*_ENABLED` config defaults (all True, and the CI compose
 * pins none of them) that the loaded page now feeds it.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, loginAsAdmin, readOpsHarness } from '../operations/harness';
import { openAdminSection } from './harness';

const harness = readOpsHarness();

const TOGGLE_IDS = [
  'vision_extraction_enabled',
  'reid_enabled',
  'scene_change_enabled',
  'clip_generation_enabled',
  'image_quality_enabled',
  'background_eval_enabled',
];

test.describe('golden path: admin settings sections load from the settings API @regression', () => {
  test.setTimeout(60_000);

  test('/settings/admin renders all four sections from its settings API response, and debug-only sections stay gated', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await loginAsAdmin(page, h);

    // Observer: the settings API's status IS the page's branch — count it so
    // this spec knows whether the sections below are the loaded page or the
    // defaults fallback. Pre-ruling-168 it asserted [500] (the fallback); the
    // fix makes a non-200 here fail loudly. The fallback claims would
    // otherwise pass on either branch — the defaults equal the config
    // defaults (measured: 60/10/10000/80, all six toggles True) — so only
    // this observer distinguishes the two.
    const settingsCalls: number[] = [];
    page.on('response', (res) => {
      try {
        if (new URL(res.url()).pathname === '/api/v1/settings') settingsCalls.push(res.status());
      } catch {
        /* non-URL-ish response */
      }
    });
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(String(e)));

    await page.goto(`${h.ui}/settings/admin`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('admin-settings')).toBeVisible();

    // The load-from-API clause: exactly one /api/v1/settings call, answered
    // 200. Ruling 168 removed the sentinel that made this route 500 (see the
    // file header), so a 500 here means the collision came back.
    await expect
      .poll(() => settingsCalls.length, { timeout: 10_000, intervals: [500] })
      .toBeGreaterThan(0);
    expect([...new Set(settingsCalls)]).toEqual([200]);

    // Loaded render, section by section (the row's named sections):
    const toggles = page.getByTestId('admin-feature-toggles');
    await expect(toggles).toBeVisible();
    await expect(toggles).toContainText('6/6 enabled'); // DEFAULT_FEATURE_TOGGLES: all true
    for (const id of TOGGLE_IDS) {
      await expect(toggles.getByTestId(`feature-toggle-${id}-switch`)).toBeVisible();
    }

    const config = page.getByTestId('admin-system-config');
    await expect(config).toBeVisible();
    await expect(config.getByTestId('input-requests-per-minute')).toHaveValue('60');
    await expect(config.getByTestId('input-burst-size')).toHaveValue('10');
    await expect(config.getByTestId('input-max-queue-size')).toHaveValue('10000');
    await expect(config.getByTestId('input-backpressure-threshold')).toHaveValue('80');
    await expect(config.getByTestId('btn-save-config')).toBeVisible();
    await expect(config.getByTestId('btn-reset-config')).toBeVisible();

    // Maintenance opens its collapsible and finds the orphan panel mounted.
    await openAdminSection(page, 'admin-maintenance', 'orphan-cleanup-panel');
    await expect(page.getByTestId('orphan-cleanup-panel')).toBeVisible();
    await expect(page.getByTestId('btn-cache-clear')).toBeVisible();
    await expect(page.getByTestId('btn-flush-queues')).toBeVisible();

    // Logging Settings is default-CLOSED (AdminSettings.tsx:194) and its
    // panel unmounts while closed (CollapsibleSection.tsx:98-114), so opening
    // it is part of the path; the card renders once its own debug/config +
    // log-level + system/config reads answer.
    await openAdminSection(page, 'admin-logging-settings', 'logging-settings');
    await expect(page.getByTestId('logging-settings')).toBeVisible();

    // Debug-gated sections: absent, not collapsed (the debugMode && gate
    // never mounts them; see header for the DEBUG=false chain).
    await expect(page.getByTestId('admin-raw-settings')).toHaveCount(0);
    await expect(page.getByTestId('admin-developer-tools')).toHaveCount(0);

    // The page rendered its loaded state with no crash: no uncaught error.
    expect(pageErrors).toEqual([]);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
