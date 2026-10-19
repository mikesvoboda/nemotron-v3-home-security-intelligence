/**
 * Uplevel F2.3 batch FE-4 — Settings page shell (`F-198`, `/settings`).
 *
 * Inventory row F-198:
 *   Surface: `/settings` (`frontend/src/App.tsx:297-315`, `frontend/src/components/settings/SettingsPage.tsx:174-238`)
 *   Action: opens `/settings`; sees the 10-tab bar (`cameras`, `rules`, `processing`,
 *           `notifications`, `ambient`, `access`, `prompts`, `storage`,
 *           `ai-models`, `admin`), secure-context banner if on HTTP, and debug-mode
 *           context from `/api/system/config`.
 *   API: `GET /api/system/config` (`frontend/src/contexts/DebugModeContext.tsx:62` ->
 *        `frontend/src/hooks/useSystemConfigQuery.ts:75-82` ->
 *        `backend/api/routes/system.py:2474-2526`).
 *
 * Nuances verified against the tree:
 * - `/settings` index route (`App.tsx:299`) immediately redirects to `/settings/cameras`.
 * - `SecureContextWarning` (`frontend/src/components/common/SecureContextWarning.tsx:32-46`)
 *   checks `window.isSecureContext` (`frontend/src/utils/webcodecs.ts:14-19`). On the
 *   feature-check loopback origin (`http://127.0.0.1:<port>`), Chromium treats `127.0.0.1`
 *   as a potentially trustworthy secure context (`window.isSecureContext === true`), so
 *   `secure-context-warning` unmounts (`count === 0`). The spec reads `window.isSecureContext`
 *   from the page and asserts the banner's presence matches `!isSecure`.
 * - Read-only surface: no server state is mutated.
 */
import { expect, test } from '../guard';
import {
  assertGuardSurvivesCameras as assertGuardSurvives,
  readHarness,
  settledGoto,
  signIn,
  type Harness,
} from '../harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

const EXPECTED_TABS = [
  { id: 'cameras', label: 'CAMERAS', path: '/settings/cameras' },
  { id: 'rules', label: 'RULES', path: '/settings/rules' },
  { id: 'processing', label: 'PROCESSING', path: '/settings/processing' },
  { id: 'notifications', label: 'NOTIFICATIONS', path: '/settings/notifications' },
  { id: 'ambient', label: 'AMBIENT', path: '/settings/ambient' },
  { id: 'access', label: 'ACCESS', path: '/settings/access' },
  { id: 'prompts', label: 'PROMPTS', path: '/settings/prompts' },
  { id: 'storage', label: 'STORAGE', path: '/settings/storage' },
  { id: 'ai-models', label: 'AI MODELS', path: '/settings/ai-models' },
  { id: 'admin', label: 'ADMIN', path: '/settings/admin' },
] as const;

test.describe('FE-4 settings shell golden path (F-198)', () => {
  test.setTimeout(60_000);

  test('F-198: /settings redirects to /settings/cameras, loads /api/system/config, and wires all 11 tabs', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/system/config (backend/api/routes/system.py:2474-2521)
    const cfgRes = await api.getJson('/api/system/config');
    expect(cfgRes.status, 'GET /api/system/config answers 200').toBe(200);
    expect(typeof cfgRes.body?.app_name).toBe('string');
    expect(typeof cfgRes.body?.version).toBe('string');
    expect(typeof cfgRes.body?.debug).toBe('boolean');
    expect(cfgRes.body?.debug, 'CI stack runs with DEBUG=false (docker-compose.ci.yml:131)').toBe(
      false
    );

    // 2. UI leg: navigate to /settings and verify index redirect to /settings/cameras
    await settledGoto(page, h, '/settings', (p) => p.getByTestId('settings-page'));
    await expect(page).toHaveURL(/\/settings\/cameras$/);

    // Shell header & subtitle (SettingsPage.tsx:184-187)
    await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible();
    await expect(page.getByText('Configure your security monitoring system')).toBeVisible();

    // SecureContextWarning (SecureContextWarning.tsx:32-46) matches !window.isSecureContext
    const isSecure = await page.evaluate(() => Boolean(window.isSecureContext));
    if (isSecure) {
      await expect(page.getByTestId('secure-context-warning')).toHaveCount(0);
    } else {
      await expect(page.getByTestId('secure-context-warning')).toBeVisible();
    }

    // Scrollable tab container & tablist (SettingsPage.tsx:78, 105-107)
    await expect(page.getByTestId('scrollable-tab-container')).toBeVisible();
    const tablist = page.getByRole('tablist', { name: 'Settings sections' });
    await expect(tablist).toBeVisible();

    // All 10 tabs from settingsTabsConfig.ts are rendered with accurate ARIA wiring
    for (const tab of EXPECTED_TABS) {
      const tabLoc = page.getByTestId(`settings-tab-${tab.id}`);
      await expect(tabLoc, `tab ${tab.id} is visible`).toBeVisible();
      await expect(tabLoc).toHaveAttribute('role', 'tab');
      await expect(tabLoc).toHaveAttribute('aria-controls', `settings-panel-${tab.id}`);
      await expect(tabLoc).toContainText(tab.label);
      const expectedSelected = tab.id === 'cameras' ? 'true' : 'false';
      await expect(tabLoc).toHaveAttribute('aria-selected', expectedSelected);
    }

    // Active tabpanel container (SettingsPage.tsx:223-235)
    const panel = page.getByTestId('settings-content-panel');
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute('role', 'tabpanel');
    await expect(panel).toHaveAttribute('id', 'settings-panel-cameras');
    await expect(panel).toHaveAttribute('aria-labelledby', 'settings-tab-cameras');

    // Switch tab to Rules and verify ARIA + route transition
    await page.getByTestId('settings-tab-rules').click();
    await expect(page).toHaveURL(/\/settings\/rules$/);
    await expect(page.getByTestId('settings-tab-rules')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('settings-tab-cameras')).toHaveAttribute(
      'aria-selected',
      'false'
    );
    await expect(panel).toHaveAttribute('id', 'settings-panel-rules');
    await expect(panel).toHaveAttribute('aria-labelledby', 'settings-tab-rules');

    await assertGuardSurvives(page, h);
  });
});
