/**
 * F-196 (inventory 3.9, seeded golden project — rulings 127, 187, 196, 217):
 * Admin › Raw settings on `/settings/admin` when the backend boots DEBUG=true.
 *
 * Two gates had to be opened before this leg could exist, one per layer:
 *
 * 1. BACKEND. The `golden` compose pins DEBUG=false (docker-compose.ci.yml:131)
 *    under OD-36, so the section never mounts. `feature-check.sh --fake
 *    --seeded` runs project `golden-seeded`, which boots DEBUG=true
 *    (scripts/feature_check.py:500-501) and matches only `*.seeded.spec.ts`.
 * 2. CLIENT. `debugMode = isDebugAvailable && storedDebugMode`
 *    (contexts/DebugModeContext.tsx:70) and storedDebugMode comes from
 *    localStorage 'system-debug-mode' with default FALSE (:63). A fresh
 *    Playwright context therefore does NOT show the section even on a
 *    DEBUG=true backend, so this leg flips the real `Toggle debug mode` switch
 *    on /operations (the same control F-133 drives) rather than writing
 *    localStorage behind the app's back — the localStorage write would pass
 *    without exercising the gate this row is about.
 *
 * The row itself has no create affordance: RawSettingsPanel renders a table of
 * existing keys with Edit/Delete per row and, when empty, a
 * "System settings will appear here when created" card
 * (RawSettingsPanel.tsx:199-209). Production code writes keys for its own
 * purposes (e.g. `gpu_assignment_strategy`, backend/api/routes/gpu_config.py:109)
 * and nothing in the harness plants one, so the key this leg edits is seeded
 * through the API first — PATCH /api/v1/system-settings/{key} is documented an
 * upsert (backend/api/routes/system_settings.py:97-110, body `{ value }` per
 * services/systemSettingsApi.ts:74-77). That mirrors the F-162 restore, which
 * likewise creates through the API what the UI cannot create, then drives the
 * UI over it.
 *
 * Cleanup is part of the contract: the key is deleted before the test ends
 * (through the UI, which is also the second half of the row), so no probe
 * setting is left in a shared boot for the legs that sort after this file.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  apiCookie,
  closedByGuard,
  loginAsAdmin,
  openAdminSection,
  readOpsHarness,
  type Session,
  type OpsHarness,
} from '../harness';

const harness = readOpsHarness();

/** Unique enough to never collide with a production key; matches ^[a-z][a-z0-9_]*$. */
const PROBE_KEY = 'golden_r196c_probe';
const SETTING_PATH = `/api/v1/system-settings/${PROBE_KEY}`;

interface SettingBody {
  key?: string;
  value?: Record<string, unknown>;
}

/**
 * Local verb helpers. operations/harness.ts exports GET/POST/DELETE only, and
 * editing that file would touch another cell's shared harness, so the two
 * calls this leg needs (an upserting PATCH and a status-only GET for the 404
 * proof) live here. Same cookie and same shape as the harness originals.
 */
async function req(
  h: OpsHarness,
  session: Session,
  method: string,
  path: string,
  body?: unknown
): Promise<{ status: number; json: unknown }> {
  const res = await fetch(`${h.api}${path}`, {
    method,
    headers: { ...apiCookie(session), 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let json: unknown = null;
  try {
    json = JSON.parse(text) as unknown;
  } catch {
    /* 204 and non-JSON answers are expected on DELETE */
  }
  return { status: res.status, json };
}

async function setting(
  h: OpsHarness,
  session: Session
): Promise<{ status: number; json: unknown }> {
  return req(h, session, 'GET', SETTING_PATH);
}

test.describe('seeded golden path: raw settings editor (F-196) @critical', () => {
  test.setTimeout(90_000);

  test('mounts Raw Settings under DEBUG=true, edits the probe key as JSON, and deletes it', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    test.info().annotations.push({
      type: 'seeded-branch',
      description: 'F-196 debug-gated Raw Settings list + JSON edit + delete',
    });

    // The backend half of the gate, read from the API the page itself reads.
    const cfg = await api<{ debug?: boolean }>(h, session, '/api/system/config');
    expect(cfg.debug).toBe(true);

    // The frontend half: a DEBUG=true backend only makes debug AVAILABLE; the
    // user toggle is what makes the sections mount. Drive the real switch.
    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    const debugSwitch = page
      .getByTestId('debug-mode-toggle')
      .getByRole('switch', { name: 'Toggle debug mode' });
    await expect(debugSwitch).toBeVisible();
    await expect(debugSwitch).toHaveAttribute('aria-checked', 'false');
    await debugSwitch.click();
    await expect(debugSwitch).toHaveAttribute('aria-checked', 'true');

    // Seed the row the editor will edit, then prove the mount is the debug
    // section's own panel and not some other card.
    const seeded = await req(h, session, 'PATCH', SETTING_PATH, {
      value: { probe: 'original' },
    });
    expect(seeded.status).toBe(200);
    expect((seeded.json as SettingBody).value).toEqual({ probe: 'original' });

    await page.goto(`${h.ui}/settings/admin`, { waitUntil: 'domcontentloaded' });
    await openAdminSection(page, 'admin-raw-settings', 'raw-settings-panel');
    const panel = page.getByTestId('raw-settings-panel');
    await expect(panel).toBeVisible();

    // The panel lists the seeded key: its per-row Edit control is keyed by the
    // key itself (RawSettingsPanel.tsx:267).
    await panel.getByTestId('raw-settings-refresh').click();
    const editRow = page.getByTestId(`raw-setting-edit-${PROBE_KEY}`);
    await expect(editRow).toBeVisible({ timeout: 15_000 });

    // Edit through the modal. The textarea arrives prefilled with
    // JSON.stringify(value, null, 2) (:73-77), so the fill replaces it rather
    // than appending.
    await editRow.click();
    const modal = page.getByTestId('edit-setting-modal');
    await expect(modal).toBeVisible();
    await page.getByTestId('edit-setting-value').fill('{\n  "probe": "edited"\n}');
    await page.getByTestId('edit-setting-save').click();

    const editToast = page
      .locator('[data-sonner-toast]')
      .filter({ hasText: `Setting "${PROBE_KEY}" updated` });
    await expect(editToast).toBeVisible({ timeout: 15_000 });

    // The value the panel saved is the value the table holds — asserted at the
    // API the panel refetches from, because the table renders the value column
    // through a formatter this spec does not own.
    const afterEdit = await setting(h, session);
    expect(afterEdit.status).toBe(200);
    expect((afterEdit.json as SettingBody).value).toEqual({ probe: 'edited' });

    // Delete through the confirm dialog, which is a second, separate dialog
    // (delete-setting-dialog), not the edit modal.
    await expect(editRow).toBeVisible();
    await page.getByTestId(`raw-setting-delete-${PROBE_KEY}`).click();
    const deleteDialog = page.getByTestId('delete-setting-dialog');
    await expect(deleteDialog).toBeVisible();
    await deleteDialog.getByTestId('delete-setting-confirm').click();

    const deleteToast = page
      .locator('[data-sonner-toast]')
      .filter({ hasText: `Setting "${PROBE_KEY}" deleted` });
    await expect(deleteToast).toBeVisible({ timeout: 15_000 });

    // Gone for the UI and gone for the API: 404 is the row's absence
    // (systemSettingsApi.ts documents 404 on a missing key).
    await expect(editRow).toHaveCount(0);
    await expect
      .poll(async () => (await setting(h, session)).status, { timeout: 15_000 })
      .toBe(404);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
