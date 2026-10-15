/**
 * F-197 (inventory 3.9, seeded golden project — rulings 127, 187, 196, 217):
 * Admin › Developer tools on `/settings/admin` when the backend boots DEBUG=true.
 *
 * Same two gates as raw-settings-edit.seeded.spec.ts (compose DEBUG=true for
 * the seeded project; the client `Toggle debug mode` switch flipped by hand,
 * because debugMode = isDebugAvailable AND localStorage 'system-debug-mode').
 *
 * Run order is measured, not assumed: `playwright test --project=golden-seeded
 * --list` runs this file FIRST of the six (workers:1, files by path,
 * 'developer-tools…' < 'orphan…' < 'raw-settings…' < 'operations/…'). So this
 * clear-all is not "the last thing in the boot" the way
 * operations/test-data.spec.ts is; it is the first. That is survivable only
 * because of what the other five legs do NOT consume — none of them needs a
 * camera or an event row (orphan cleanup and recording replay read files on
 * disk, raw settings writes its own key, circuit-breaker-reset reads
 * /api/system/circuit-breakers, debug-mode-toggle reads /api/system/config) —
 * and because the restore below returns the boot to its stated invariant:
 * harness cameras with stable ids, events and detections back to zero
 * (operations/test-data.spec.ts:33-40). Even a failure between the clear and
 * the restore leaves no later leg starved, since no later leg reads cameras.
 *
 * The row's warning is explicit — "Clear All Test Data" deletes ALL cameras,
 * events and detections, not only seeded ones (AdminSettings.tsx:971-974), and
 * the inventory repeats it. The restore mechanism is copied from
 * test-data.spec.ts:195-253: the harness's camera book (FEATURE_CHECK_CAMERAS,
 * written unconditionally at scripts/feature_check.py:2106 — seeded runs
 * included) names every camera the boot registered, and camera ids are
 * slug-derived and STABLE across delete+recreate, so re-POSTing each name must
 * return the recorded id. The leg skips unless that book is exported: the
 * restore contract is not optional.
 */
import { readFileSync } from 'node:fs';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  authPost,
  closedByGuard,
  loginAsAdmin,
  openAdminSection,
  pollApi,
  readOpsHarness,
} from './harness';

const harness = readOpsHarness();
const CAMERAS_FILE = process.env.FEATURE_CHECK_CAMERAS ?? '';
const CAMERA_TARGET = '/cameras'; // the watcher's root inside the backend container

interface CameraList {
  items?: { id: string }[];
  pagination?: { total?: number };
}

interface EventList {
  pagination?: { total?: number };
}

/**
 * Camera total at the API the app reads. items.length when the envelope omits
 * pagination, pagination.total when it carries one (CameraListResponse,
 * backend/api/schemas/camera.py:396).
 */
function total(body: CameraList): number {
  return body.pagination?.total ?? body.items?.length ?? 0;
}

test.describe('seeded golden path: developer tools seed and clear (F-197) @critical', () => {
  test.setTimeout(120_000);

  test('seeds cameras and events from Developer Tools, clears all test data, restores the harness cameras', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    test
      .info()
      .skip(
        !CAMERAS_FILE,
        'destructive row needs FEATURE_CHECK_CAMERAS so it can restore afterwards'
      );
    if (!harness.ready || !CAMERAS_FILE) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    test.info().annotations.push({
      type: 'seeded-branch',
      description: 'F-197 debug-gated Developer Tools: seed 5 + seed 50 + typed clear + restore',
    });

    const book = JSON.parse(readFileSync(CAMERAS_FILE, 'utf8')) as Record<string, string>;
    expect(Object.keys(book).length).toBeGreaterThan(0);

    const cfg = await api<{ debug?: boolean }>(h, session, '/api/system/config');
    expect(cfg.debug).toBe(true);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    const debugSwitch = page
      .getByTestId('debug-mode-toggle')
      .getByRole('switch', { name: 'Toggle debug mode' });
    await expect(debugSwitch).toBeVisible();
    await expect(debugSwitch).toHaveAttribute('aria-checked', 'false');
    await debugSwitch.click();
    await expect(debugSwitch).toHaveAttribute('aria-checked', 'true');

    // Baselines read before anything is added, so the toast counts below are
    // arithmetically checked rather than matched on a permissive \d+. The boot
    // already registered the scenario cameras (feature_check.py:2093-2106) and
    // AdminSettings' button sends the fixed sample set (AdminSettings.tsx:380
    // count:5, :396 count:50), whose names do not overlap the scenario names —
    // but seed_cameras skips existing names and counts only new rows
    // (admin.py:341-366), so 0 is an HONEST answer here and the precedent
    // test-data.spec.ts:118-125 says so. Reading the delta is what lets this
    // leg distinguish "5 new cameras" from "0 because they already existed"
    // without pinning a number the stack is allowed to answer differently.
    const camerasBefore = total(await api<CameraList>(h, session, '/api/cameras'));
    const eventsBefore = (await api<EventList>(h, session, '/api/events?limit=1')).pagination
      ?.total;

    await page.goto(`${h.ui}/settings/admin`, { waitUntil: 'domcontentloaded' });
    await openAdminSection(page, 'admin-developer-tools', 'btn-seed-cameras');

    // --- Seed Test Cameras: behind a plain ConfirmDialog (jobs/ConfirmDialog
    // .tsx), whose confirm button label IS the accessible name ("Seed
    // Cameras"), unlike the typed dialog below.
    await page.getByTestId('btn-seed-cameras').click();
    const cameraDialog = page.getByTestId('confirm-dialog');
    await expect(cameraDialog).toBeVisible();
    await expect(cameraDialog).toContainText('Seed Test Cameras');
    await cameraDialog.getByRole('button', { name: 'Seed Cameras', exact: true }).click();
    const seedCamerasToast = page
      .locator('[data-sonner-toast]')
      .filter({ hasText: /Created \d+ cameras/ });
    await expect(seedCamerasToast).toBeVisible({ timeout: 20_000 });
    // Captured NOW, while it is on screen: textContent, not Locator.toString()
    // (the latter renders the SELECTOR string, so a regex over it can never see
    // the number the user was shown), and read before any await that could let
    // sonner dismiss it rather than re-resolving the locator later.
    const toastText = (await seedCamerasToast.textContent()) ?? '';

    const camerasAfterSeed = total(await api<CameraList>(h, session, '/api/cameras'));
    expect(camerasAfterSeed).toBeGreaterThanOrEqual(camerasBefore);
    // The number the toast showed is the number of rows the table gained — the
    // same "the toast must not lie" discipline as admin-cache-clear.spec.ts:89,
    // which compares the toast against the endpoint's own count.
    const promised = /Created (\d+) cameras/.exec(toastText)?.[1];
    expect(promised).toBeDefined();
    expect(camerasAfterSeed - camerasBefore).toBe(Number(promised));

    // --- Seed Test Events: needs cameras first (admin.py:450 docstring), which
    // the leg above just guaranteed.
    await page.getByTestId('btn-seed-events').click();
    const eventDialog = page.getByTestId('confirm-dialog');
    await expect(eventDialog).toContainText('Seed Test Events');
    await eventDialog.getByRole('button', { name: 'Seed Events', exact: true }).click();
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: /Created \d+ events/ })
    ).toBeVisible({ timeout: 20_000 });

    // Events really landed (50, per the handler's fixed count).
    await pollApi<EventList>(
      h,
      session,
      '/api/events?limit=1',
      (b) => (b.pagination?.total ?? 0) > (eventsBefore ?? 0),
      20_000
    );

    // --- Clear All Test Data: the ConfirmWithTextDialog gate. Its confirm
    // Button carries NO data-testid (components/developer-tools/
    // ConfirmWithTextDialog.tsx), so it is selected by name, and it is
    // disabled until the input holds the exact literal "DELETE" — note this is
    // the UI token, distinct from the wire token 'DELETE_ALL_DATA' the handler
    // sends (AdminSettings.tsx:412). Asserting the disabled gate is the point:
    // it is the only thing standing between one click and a wiped database.
    await page.getByTestId('btn-clear-test-data').click();
    const clearDialog = page.locator('[role="dialog"]');
    await expect(clearDialog).toBeVisible();
    const clearButton = clearDialog.getByRole('button', { name: 'Clear All Data', exact: true });
    await expect(clearButton).toBeDisabled();
    await clearDialog.getByPlaceholder('Type "DELETE"').fill('DELETE');
    await expect(clearButton).toBeEnabled();
    await clearButton.click();

    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: /Test data cleared/ })
    ).toBeVisible({ timeout: 20_000 });

    // The wipe is real at the API, not just in the toast.
    await expect
      .poll(async () => total(await api<CameraList>(h, session, '/api/cameras')), {
        timeout: 20_000,
      })
      .toBe(0);

    // --- Restore. Recreate every camera from the book by name; slug-derived
    // ids are stable across delete+recreate, so each POST must answer the id
    // the boot recorded. This is what makes the row legal to run in a shared
    // boot (test-data.spec.ts:33-40, :232-239).
    for (const [name, expectedId] of Object.entries(book)) {
      const created = await authPost<{ id: string }>(h, session, '/api/cameras', {
        name,
        folder_path: `${CAMERA_TARGET}/${name}`,
      });
      expect(created.id).toBe(expectedId);
    }

    // Polled, not read-once: the measured stale-read lag after a clear means a
    // single immediate read proves nothing about the commit.
    await expect
      .poll(async () => total(await api<CameraList>(h, session, '/api/cameras')), {
        timeout: 20_000,
      })
      .toBe(Object.keys(book).length);
    await pollApi<EventList>(
      h,
      session,
      '/api/events?limit=1',
      (b) => (b.pagination?.total ?? 0) === 0,
      20_000
    );

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
