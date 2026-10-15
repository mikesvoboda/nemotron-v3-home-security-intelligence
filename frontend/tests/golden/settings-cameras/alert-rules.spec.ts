/**
 * Uplevel F2.3 batch FE-4 — Alert Rules: Rule List & Severity Reference, Delete Rule, Test Rule
 * (`F-215`, `F-218`, `F-219`, `/settings/rules`).
 *
 * Inventory rows covered:
 * - F-215: Alert rules › rule list and severity reference (`/settings/rules`,
 *          `GET /api/alerts/rules`, `GET /api/cameras`, `GET /api/system/severity`)
 * - F-218: Alert rules › Delete rule (`/settings/rules`, `DELETE /api/alerts/rules/{rule_id}`)
 * - F-219: Alert rules › Test rule modal (`/settings/rules`, `POST /api/alerts/rules/{rule_id}/test`)
 *
 * Key implementation details verified against the tree:
 * - `AlertRulesSettings.tsx:496-501` mounts `<SeverityConfigPanel />`
 *   (`frontend/src/components/system/SeverityConfigPanel.tsx:85`), which renders
 *   `data-testid="severity-config-panel"`, `Read-only` badge, 4 severity level rows
 *   (`severity-level-critical`, `severity-level-high`, `severity-level-medium`,
 *   `severity-level-low`), score ranges (`score-range-${sev}`), and threshold values
 *   (`threshold-low-max`, `threshold-medium-max`, `threshold-high-max`).
 * - Because the clean CI stack seeds no `alert_rules` rows and `F-216`/`F-217` (UI rule
 *   creation/toggling) are ruled `half-built`, each test snapshots `beforeIds`, seeds its
 *   own fixture rule via `POST /api/alerts/rules` (`backend/api/routes/alerts.py:184`),
 *   drives the UI surface, and restores `alertRuleIds` to `beforeIds` in `finally`.
 */
import { expect, test } from '../guard';
import {
  alertRuleIds,
  apiPath,
  assertGuardSurvives,
  deleteAlertRuleIfPresent,
  readHarness,
  settledGoto,
  signIn,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

test.describe('FE-4 alert rules golden path (F-215, F-218, F-219)', () => {
  test.setTimeout(90_000);

  test('F-215: /settings/rules renders read-only SeverityConfigPanel from GET /api/system/severity and rule list from GET /api/alerts/rules', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/system/severity (backend/api/routes/system.py:3506-3555)
    const sevRes = await api.getJson('/api/system/severity');
    expect(sevRes.status, 'GET /api/system/severity answers 200').toBe(200);
    const definitions = Array.isArray(sevRes.body?.definitions) ? sevRes.body.definitions : [];
    expect(definitions.length).toBe(4);
    const thresholds = sevRes.body?.thresholds as {
      low_max: number;
      medium_max: number;
      high_max: number;
    };
    expect(typeof thresholds?.low_max).toBe('number');
    expect(typeof thresholds?.medium_max).toBe('number');
    expect(typeof thresholds?.high_max).toBe('number');

    const beforeIds = await alertRuleIds(api);
    const runTag = Date.now().toString(36);
    const ruleName = `Golden FE4 F215 Rule ${runTag}`;
    const ruleDesc = `High severity night schedule rule ${runTag}`;
    let ruleId: string | null = null;

    try {
      // Seed fixture rule via POST /api/alerts/rules (backend/api/routes/alerts.py:184)
      const createRes = await api.send('/api/alerts/rules', 'POST', {
        name: ruleName,
        description: ruleDesc,
        enabled: true,
        severity: 'high',
        risk_threshold: 60,
        schedule: {
          days: ['monday', 'wednesday'],
          start_time: '22:00',
          end_time: '06:00',
          timezone: 'UTC',
        },
        channels: ['email', 'webhook'],
        cooldown_seconds: 300,
      });
      expect(createRes.status, 'POST /api/alerts/rules answers 201').toBe(201);
      ruleId = String(createRes.body?.id);

      // 2. Navigate to /settings/rules and wait for SeverityConfigPanel + rule row
      await settledGoto(page, h, '/settings/rules', (p) => p.getByTestId('severity-config-panel'));

      // Verify SeverityConfigPanel (SeverityConfigPanel.tsx:85-189) mirrors GET /api/system/severity
      const sevPanel = page.getByTestId('severity-config-panel');
      await expect(sevPanel).toBeVisible();
      await expect(sevPanel.getByText('Severity Configuration', { exact: true })).toBeVisible();
      await expect(sevPanel.getByText('Read-only', { exact: true })).toBeVisible();

      for (const def of definitions as {
        severity: string;
        min_score: number;
        max_score: number;
      }[]) {
        await expect(sevPanel.getByTestId(`severity-level-${def.severity}`)).toBeVisible();
        await expect(sevPanel.getByTestId(`score-range-${def.severity}`)).toHaveText(
          `${def.min_score}-${def.max_score}`
        );
      }

      await expect(sevPanel.getByTestId('threshold-low-max')).toHaveText(
        String(thresholds.low_max)
      );
      await expect(sevPanel.getByTestId('threshold-medium-max')).toHaveText(
        String(thresholds.medium_max)
      );
      await expect(sevPanel.getByTestId('threshold-high-max')).toHaveText(
        String(thresholds.high_max)
      );

      // Verify Alert Rules table row (AlertRulesSettings.tsx:522-652)
      await expect(page.getByRole('heading', { name: 'Alert Rules', exact: true })).toBeVisible();
      const row = page.locator('tbody tr').filter({ hasText: ruleName });
      await expect(row).toBeVisible();
      await expect(row).toContainText(ruleName);
      await expect(row).toContainText(ruleDesc);
      await expect(row).toContainText('High');
      await expect(row).toContainText('Mon, Wed, 22:00 - 06:00');
      await expect(row).toContainText('email');
      await expect(row).toContainText('webhook');

      const toggleSwitch = row.getByRole('switch', {
        name: `Toggle ${ruleName} rule off`,
      });
      await expect(toggleSwitch).toBeVisible();
      await expect(toggleSwitch).toHaveAttribute('aria-checked', 'true');

      await assertGuardSurvives(page, h);
    } finally {
      if (ruleId) {
        await deleteAlertRuleIfPresent(api, ruleId);
      }
      expect(await alertRuleIds(api)).toEqual(beforeIds);
    }
  });

  test('F-218: Delete Alert Rule modal cancels without deleting and confirms via DELETE /api/alerts/rules/{id}', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const beforeIds = await alertRuleIds(api);
    const runTag = Date.now().toString(36);
    const ruleName = `Golden FE4 F218 Delete ${runTag}`;
    let ruleId: string | null = null;

    try {
      const createRes = await api.send('/api/alerts/rules', 'POST', {
        name: ruleName,
        enabled: true,
        severity: 'medium',
        channels: ['webhook'],
        cooldown_seconds: 300,
      });
      expect(createRes.status, 'POST /api/alerts/rules answers 201').toBe(201);
      ruleId = String(createRes.body?.id);

      await settledGoto(page, h, '/settings/rules', (p) =>
        p.locator('tbody tr').filter({ hasText: ruleName })
      );

      const row = page.locator('tbody tr').filter({ hasText: ruleName });
      await expect(row).toBeVisible();

      // --- Arm 1: Cancel keeps the rule intact (AlertRulesSettings.tsx:1107-1175) ---
      await row.getByRole('button', { name: `Delete ${ruleName}`, exact: true }).click();
      const dialog = page.getByRole('dialog', { name: 'Delete Alert Rule' });
      await expect(dialog.getByRole('heading', { name: 'Delete Alert Rule' })).toBeVisible();
      await expect(
        dialog.getByText(
          `Are you sure you want to delete ${ruleName}? This action cannot be undone.`
        )
      ).toBeVisible();
      await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await expect(row).toBeVisible();

      const stillThere = await api.getJson(`/api/alerts/rules/${ruleId}`);
      expect(stillThere.status, 'rule remains after Cancel').toBe(200);

      // --- Arm 2: Confirm sends DELETE /api/alerts/rules/{id} (204) and removes the row ---
      await row.getByRole('button', { name: `Delete ${ruleName}`, exact: true }).click();
      await expect(dialog.getByRole('heading', { name: 'Delete Alert Rule' })).toBeVisible();

      const deletePromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/alerts/rules/${ruleId}` &&
          res.request().method() === 'DELETE'
      );
      const refetchPromise = page.waitForResponse(
        (res) => apiPath(res.url()) === '/api/alerts/rules' && res.request().method() === 'GET'
      );
      await dialog.getByRole('button', { name: 'Delete Rule', exact: true }).click();
      const [deleteRes, refetchRes] = await Promise.all([deletePromise, refetchPromise]);
      expect(deleteRes.status(), 'DELETE /api/alerts/rules/{id} answers 204').toBe(204);
      expect(refetchRes.status(), 'GET /api/alerts/rules refetch answers 200').toBe(200);

      await expect(dialog).toHaveCount(0);
      await expect(row).toHaveCount(0);

      const afterGet = await api.getJson(`/api/alerts/rules/${ruleId}`);
      expect(afterGet.status, 'deleted rule answers 404').toBe(404);
      ruleId = null;

      await assertGuardSurvives(page, h);
    } finally {
      if (ruleId) {
        await deleteAlertRuleIfPresent(api, ruleId);
      }
      expect(await alertRuleIds(api)).toEqual(beforeIds);
    }
  });

  test('F-219: Test Rule modal calls POST /api/alerts/rules/{id}/test and displays event match results', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const beforeIds = await alertRuleIds(api);
    const runTag = Date.now().toString(36);
    const ruleName = `Golden FE4 F219 Test ${runTag}`;
    let ruleId: string | null = null;

    try {
      // Seed rule with risk_threshold: 50 so it matches the harness smoke event (risk_score: 61)
      const createRes = await api.send('/api/alerts/rules', 'POST', {
        name: ruleName,
        enabled: true,
        severity: 'high',
        risk_threshold: 50,
        channels: ['email'],
        cooldown_seconds: 300,
      });
      expect(createRes.status, 'POST /api/alerts/rules answers 201').toBe(201);
      ruleId = String(createRes.body?.id);

      // 1. API-first check: POST /api/alerts/rules/{id}/test (backend/api/routes/alerts.py:430-506)
      const apiTestRes = await api.send(`/api/alerts/rules/${ruleId}/test`, 'POST', {
        limit: 10,
      });
      expect(apiTestRes.status, 'POST /api/alerts/rules/{id}/test answers 200').toBe(200);
      expect(apiTestRes.body?.rule_id).toBe(ruleId);
      expect(apiTestRes.body?.rule_name).toBe(ruleName);
      const eventsTested = Number(apiTestRes.body?.events_tested ?? 0);
      const eventsMatched = Number(apiTestRes.body?.events_matched ?? 0);
      const matchRatePct = `${(Number(apiTestRes.body?.match_rate ?? 0) * 100).toFixed(0)}%`;
      const results = Array.isArray(apiTestRes.body?.results) ? apiTestRes.body.results : [];

      // 2. UI leg: click Test button on rule row (AlertRulesSettings.tsx:628-635, 1178-1315)
      await settledGoto(page, h, '/settings/rules', (p) =>
        p.locator('tbody tr').filter({ hasText: ruleName })
      );

      const row = page.locator('tbody tr').filter({ hasText: ruleName });
      const testPostPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/alerts/rules/${ruleId}/test` &&
          res.request().method() === 'POST'
      );
      await row.getByRole('button', { name: `Test ${ruleName}`, exact: true }).click();
      const testPostRes = await testPostPromise;
      expect(testPostRes.status()).toBe(200);
      expect(testPostRes.request().postDataJSON()).toEqual({ limit: 10 });

      const dialog = page.getByRole('dialog', { name: `Test Rule: ${ruleName}` });
      await expect(dialog.getByRole('heading', { name: `Test Rule: ${ruleName}` })).toBeVisible();
      await expect(dialog.getByText('Events Tested')).toBeVisible();
      await expect(dialog.getByText('Matched', { exact: true })).toBeVisible();
      await expect(dialog.getByText('Match Rate')).toBeVisible();
      await expect(dialog.getByText(String(eventsTested)).first()).toBeVisible();
      await expect(dialog.getByText(String(eventsMatched)).first()).toBeVisible();
      await expect(dialog.getByText(matchRatePct)).toBeVisible();

      if (eventsTested > 0 && results.length > 0) {
        await expect(dialog.getByText('Event Results')).toBeVisible();
        const first = results[0] as {
          event_id: number;
          risk_score: number | null;
          matches: boolean;
          matched_conditions: string[];
        };
        await expect(dialog.getByText(`Event #${first.event_id}`)).toBeVisible();
        await expect(dialog.getByText(`Risk: ${first.risk_score ?? 'N/A'}`).first()).toBeVisible();
        if (first.matches && first.matched_conditions.length > 0) {
          await expect(
            dialog.getByText(`Matched: ${first.matched_conditions.join(', ')}`).first()
          ).toBeVisible();
        }
      } else {
        await expect(dialog.getByText('No recent events to test against')).toBeVisible();
      }

      await dialog.getByRole('button', { name: 'Close', exact: true }).click();
      await expect(dialog).toHaveCount(0);

      await assertGuardSurvives(page, h);
    } finally {
      if (ruleId) {
        await deleteAlertRuleIfPresent(api, ruleId);
      }
      expect(await alertRuleIds(api)).toEqual(beforeIds);
    }
  });
});
