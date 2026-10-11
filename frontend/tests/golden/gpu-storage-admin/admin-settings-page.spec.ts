/**
 * F-187 (inventory 3.9): the Admin Settings page at /settings/admin — a
 * scoped partial of the row, with its load-from-API clause cited for
 * demotion.
 *
 * The row's core clause is "sections load from the settings API", and that
 * clause is dead on EVERY stack the app ships (measured at origin/main
 * b1e3af4e0, all four files byte-identical at this batch's merge-base):
 * GET /api/v1/settings answers 500 — settings_api.py:115 feeds
 * settings.fast_path_confidence_threshold (backend/core/config.py:1966,
 * default=2.0 with the deliberate "DISABLED — set to impossible value (>1.0)"
 * note, le=10.0) into DetectionSettings.fast_path_threshold, whose schema
 * caps it at le=1.0 (backend/api/schemas/settings_api.py:49) — pydantic
 * rejects its own default and the route never returns. F-187 therefore
 * demotes; what IS still true, and what this spec pins, is the page's
 * designed response to that failure: AdminSettings falls back to
 * DEFAULT_FEATURE_TOGGLES when settings is undefined (AdminSettings.tsx:237
 * -249) and renders DEFAULT_SYSTEM_CONFIG (:163-173, :211-212) instead of an
 * error screen, with no page error.
 *
 * The row's debug-mode parenthetical is ALSO pinned false here: Raw Settings
 * and Developer Tools mount only under debugMode (:787, :805), and
 * DebugModeContext forces debugMode false whenever the backend reports
 * debug=false ("When isDebugAvailable is false, debugMode will always be
 * false regardless of localStorage", DebugModeContext.tsx:10-11) — the CI
 * compose pins DEBUG=false (docker-compose.ci.yml:131). The F-196/F-197
 * demotions cite the same gate.
 *
 * The spec also counts the six toggle switches, because the row's
 * "6/6 enabled" section summary is an arithmetic on FEATURE_TOGGLE_CONFIGS
 * (:84) and DEFAULT_FEATURE_TOGGLES (:140) that only holds on the fallback
 * path this page is actually on.
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

test.describe('golden path: admin settings sections render on their defaults fallback @regression', () => {
  test.setTimeout(60_000);

  test('/settings/admin renders all four sections from built-in defaults while its settings API 500s, and debug-only sections stay gated', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await loginAsAdmin(page, h);

    // Observer: the settings 500 IS the page's reality — count it so this
    // spec fails LOUDLY the day someone fixes the schema collision (the
    // page's fallback claims below would still pass silently otherwise).
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
    // 500. When the backend is fixed this fails, pointing at this spec —
    // which is the intent: the row re-enters F2.3 the day the API works.
    await expect
      .poll(() => settingsCalls.length, { timeout: 10_000, intervals: [500] })
      .toBeGreaterThan(0);
    expect([...new Set(settingsCalls)]).toEqual([500]);

    // Fallback render, section by section (the row's named sections):
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

    // The page survived its failed API with no crash: no uncaught error.
    expect(pageErrors).toEqual([]);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
