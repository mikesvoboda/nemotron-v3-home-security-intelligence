/**
 * F-158 (inventory 3.8): the Configuration Inspector on /operations lists the
 * application's SETTINGS, not the HTTP envelope that carries them.
 *
 * Why this spec exists: GET /api/debug/config answers the envelope
 * { config, timestamp } (backend/api/routes/debug.py:527), and useDebugConfigQuery
 * derived its table from Object.entries of the WHOLE body — so the panel rendered
 * exactly two rows named `config` and `timestamp`, and its redaction could never
 * fire because neither envelope value is '[REDACTED]'. The unit tier stayed green
 * through that because its hand-written mirror type was `Record<string, unknown>`,
 * which accepts every shape (the type-level equivalent of a mock). A real browser
 * against the real backend is the tier that can see the difference.
 *
 * Two legs, one run, cross-bound — the shape the other operations specs use:
 *   NODE  reads /api/debug/config through the forwarder and reports the true
 *         shape: the envelope's keys, how many settings `config` holds, and WHICH
 *         key answers '[REDACTED]'.
 *   BROWSER reads the panel's rendered rows and is asserted against the NODE
 *         numbers, so the row count and the redacted cell's identity come from
 *         the same stack's measurement rather than from a constant in this file.
 *
 * What would make this green by accident, and what stops it:
 *  - a hard-coded 'WARNING' would be a tautology (the card's own defaults are
 *    also plausible strings) → the log_level cell is compared to cfg.log_level.
 *  - asserting the text 'config'/'timestamp' is absent would false-fail (nested
 *    settings values contain those words) → the ABSENCE is asserted on the row
 *    testids `value-config`/`value-timestamp` and on tbody row count.
 *  - a redaction asserted on a key name picked in this file could pass while the
 *    real masked key moved → redactedKey is recovered from the node leg.
 *
 * The `database_url` leg pins a DECISION, not just a rendering: the backend masks
 * only the password inside a DSN (debug.py:350), so that value is NOT flagged
 * sensitive and the operator can still read host and db. A regex-based
 * isSensitive would grey it out; this row would then fail.
 *
 * The section is default-COLLAPSED (useSystemPageSections.ts:68), so opening it is
 * part of the path. The panel is NOT gated on the frontend debug-mode flag, so
 * nothing is seeded beyond the tour keys the golden guard already writes.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, closedByGuard, loginAsAdmin, openSection, readOpsHarness } from '../harness';

const harness = readOpsHarness();

interface DebugConfigEnvelope {
  config?: Record<string, unknown>;
  timestamp?: string;
}

function isRedacted(value: unknown): boolean {
  return value === '[REDACTED]';
}

test.describe('golden path: configuration inspector lists settings (F-158) @critical', () => {
  test.setTimeout(90_000);

  test('the table lists the settings map, not the envelope, and flags masked values', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));

    const session = await loginAsAdmin(page, h);

    // ── NODE LEG ────────────────────────────────────────────────────────────
    // The contract the UI is measured against. If this endpoint ever stops
    // answering as an envelope, this spec fails HERE and says so, instead of a
    // UI assertion failing for a reason the reader has to re-derive.
    const body = await api<DebugConfigEnvelope>(h, session, '/api/debug/config');
    expect(Object.keys(body).sort()).toEqual(['config', 'timestamp']);
    const cfg = body.config;
    expect(cfg, 'response carried no `config` settings map').toBeTruthy();

    const settingsKeys = Object.keys(cfg as Record<string, unknown>);
    expect(settingsKeys.length, 'settings map looks implausibly small').toBeGreaterThan(50);

    // Which key does the backend itself mask? Sorted so the pick is stable.
    const redactedKey = settingsKeys
      .filter((k) => isRedacted((cfg as Record<string, unknown>)[k]))
      .sort()[0];
    expect(redactedKey, 'no setting answered exactly [REDACTED]').toBeTruthy();

    const logLevel = (cfg as Record<string, unknown>).log_level;
    expect(String(logLevel)).toMatch(/^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$/);

    // ── BROWSER LEG ─────────────────────────────────────────────────────────
    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'config-inspector');

    // The panel is scoped through its SECTION root, not a panel testid, because
    // the panel testid the page asks for does not exist: SystemMonitoringPage.tsx:738
    // passes data-testid="config-inspector-panel-section" to ConfigInspectorPanel,
    // which accepts `_props` (:73) and never spreads it — its root <div> (:135) has
    // no testid, so the prop is dropped. Every locator below therefore hangs off
    // the section root, whose toggle is the root's only other child and carries no
    // rows, so the row assertions below are unique to the panel. If someone fixes
    // the dropped prop, the count-0 assertion directly below fails and points here.
    const panel = page.getByTestId('config-inspector-section');
    await expect(panel.getByRole('heading', { name: 'Configuration Inspector' })).toBeVisible();
    await expect(page.getByTestId('config-inspector-panel-section')).toHaveCount(0);

    // Success render: the loading branch (config-loading) is replaced by rows
    // only after the real fetch answered. Generous budget: first compile of this
    // route is the slow leg on a cold dev server.
    const firstRow = panel.getByTestId(`value-${settingsKeys[0]}`);
    await expect(firstRow).toBeVisible({ timeout: 30_000 });

    // THE FIX, MEASURED: one row per setting. Before it the table had exactly 2
    // rows — `config` and `timestamp` — so this comparison is the discriminator
    // and it is bound to a number from the same run, not to a literal.
    const rowCount = await panel.locator('tbody tr').count();
    expect(rowCount).toBe(settingsKeys.length);

    // The envelope is not settings, so it is not in the table.
    await expect(panel.getByTestId('value-config')).toHaveCount(0);
    await expect(panel.getByTestId('value-timestamp')).toHaveCount(0);

    // A setting the card elsewhere displays is present HERE with the backend's
    // value (measured: the stack answers WARNING while LoggingSettings displayed
    // its 'INFO' default — same envelope-vs-payload bug, second victim).
    await expect(panel.getByTestId('value-log_level')).toHaveText(String(logLevel));

    // Redaction: the exact key the backend masked is italic-flagged in the DOM.
    const redactedCell = panel.locator(
      `[data-testid="value-${redactedKey}"][data-sensitive="true"]`
    );
    await expect(redactedCell).toHaveCount(1);
    await expect(redactedCell).toHaveText('[REDACTED]');

    // The partial mask stays readable on purpose (debug.py:350 masks the
    // password only). Flagged-sensitive here would grey out what the operator
    // is meant to read, so this row asserts the OPPOSITE of the redacted one.
    const dsn = (cfg as Record<string, unknown>).database_url;
    if (typeof dsn === 'string' && dsn.includes('[REDACTED]') && dsn !== '[REDACTED]') {
      const cell = panel.getByTestId('value-database_url');
      await expect(cell).toHaveText(dsn);
      await expect(
        panel.locator('[data-testid="value-database_url"][data-sensitive="true"]')
      ).toHaveCount(0);
    }

    expect(pageErrors, `page crashed: ${pageErrors.join(' | ')}`).toEqual([]);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
