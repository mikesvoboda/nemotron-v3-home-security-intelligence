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
 * The row's warning is explicit — the dialog states "permanently delete ALL
 * cameras, events, and detections" (AdminSettings.tsx:983-984) and the card's
 * own summary says "Delete all cameras, events, and detections" (:903), not
 * only seeded ones; the inventory repeats it. The restore mechanism is copied from
 * test-data.spec.ts:195-253: the harness's camera book (FEATURE_CHECK_CAMERAS,
 * written unconditionally at scripts/feature_check.py:2106 — seeded runs
 * included) names every camera the boot registered, and camera ids are
 * slug-derived and STABLE across delete+recreate, so re-POSTing each name must
 * return the recorded id. The leg skips unless that book is exported: the
 * restore contract is not optional.
 *
 * READS THAT OBSERVE A MUTATION GO PER-ID, NOT OVER THE CAMERA LIST. The camera
 * LIST (GET /api/cameras) is cache-aside over Redis for SHORT_TTL=60s
 * (cameras.py:261), and NEITHER seed_cameras NOR clear_seeded_data invalidates
 * it — only /maintenance/clear-cache does (admin.py:1134). The create/update/
 * delete handlers in cameras.py each schedule their own invalidation
 * (create_camera :815, update_camera :913, delete_camera :992 — plus
 * restore_camera :657); the admin seed+clear paths do not. So the first CI run of
 * this leg (job 116664916467, run 38804341602, head 0642f8348) reddened at the
 * seed count DELTA with OPPOSITE signs on consecutive retries — attempt1
 * Expected 5 / Received 0, retry1 Expected 0 / Received 5, retry2 Expected 5 /
 * Received 0 — which is two reads of one cached key straddling a 60 s expiry,
 * not arithmetic (a wrong formula fails identically every retry). Every check
 * below that asks "did this seed/clear/restore change the row set?" therefore
 * probes GET /api/cameras/{id} per id: get_camera (cameras.py:684) injects only
 * db:DbSession, takes no CacheDep, reads the table directly, and 404s on
 * absence. Do NOT "simplify" this back to a list total — that reintroduces the
 * stale-read red. The events LIST is not cached (list_events makes no cache
 * call; only /stats and /timeline-summary do) so the event polls keep using it.
 */
import { readFileSync } from 'node:fs';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  apiCookie,
  authPost,
  closedByGuard,
  loginAsAdmin,
  openAdminSection,
  pollApi,
  readOpsHarness,
  type OpsHarness,
  type Session,
} from './harness';

const harness = readOpsHarness();
const CAMERAS_FILE = process.env.FEATURE_CHECK_CAMERAS ?? '';
const CAMERA_TARGET = '/cameras'; // the watcher's root inside the backend container

interface EventList {
  pagination?: { total?: number };
}

/** The five cameras the Developer Tools seed button creates, in
 * _get_sample_cameras order (admin.py:170-207 — six entries, living-room last), stored under these DASHED ids
 * verbatim by seed_cameras (admin.py:359-360). Copied from the F-160 precedent's
 * asserted set (test-data.spec.ts:135), which measured them after a first draft
 * wrongly expected slugified ids. */
const SAMPLE_IDS = ['front-door', 'backyard', 'garage', 'driveway', 'side-gate'];

/**
 * Cache-immune per-row existence. GET /api/cameras/{id} is get_camera
 * (cameras.py:684): it injects only db:DbSession — no CacheDep — and looks the
 * row up with Camera.id == camera_id and NO id normalization
 * (dependencies.py:459), so it reads the table directly and is unaffected by the
 * camera-LIST Redis cache (SHORT_TTL=60s) that seed/clear never invalidate.
 * 200 → present, 404 → absent; any other status throws (that is not a "row is
 * missing" answer and must not be swallowed as absence). This is the primitive
 * every mutation-observing check in this leg uses — a list total would read
 * through a cached entry the mutation did not touch.
 */
async function cameraExists(h: OpsHarness, session: Session, id: string): Promise<boolean> {
  const res = await fetch(`${h.api}/api/cameras/${encodeURIComponent(id)}`, {
    headers: apiCookie(session),
  });
  if (res.status === 200) return true;
  if (res.status === 404) return false;
  throw new Error(
    `GET /api/cameras/${id} answered ${res.status}: ${(await res.text()).slice(0, 200)}`
  );
}

/** How many of `ids` exist right now, read straight from the table. */
async function countPresentCameras(
  h: OpsHarness,
  session: Session,
  ids: string[]
): Promise<number> {
  const present = await Promise.all(ids.map((id) => cameraExists(h, session, id)));
  return present.filter(Boolean).length;
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

    // Baselines read before anything is added, so the toast count below is
    // arithmetically checked rather than matched on a permissive \d+. The boot
    // already registered the scenario cameras (feature_check.py:2093-2106) and
    // AdminSettings' button sends the fixed sample set (AdminSettings.tsx:380
    // count:5), whose names do not overlap the scenario names — but seed_cameras
    // skips existing ids and counts only new rows (admin.py:342-366), so 0 is an
    // HONEST answer here and the precedent test-data.spec.ts:118-125 says so.
    // The delta is taken over PER-ID reads, not the list total: on a retry the
    // sample ids already exist, so a genuine "created 0" must be observable as
    // "0 newly present" rather than being lost in a list count the seed did not
    // change.
    const camerasBefore = await countPresentCameras(h, session, SAMPLE_IDS);
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

    // The number the toast showed is the number of sample cameras the table
    // gained — the same "the toast must not lie" discipline as
    // admin-cache-clear.spec.ts:89, which compares the toast against the
    // endpoint's own count. Read per-id, not as a list total: the list is
    // cached for SHORT_TTL=60s and seed_cameras never invalidates it, so a list
    // delta reads a stale snapshot (this leg's first CI run failed exactly
    // there, with opposite signs on consecutive retries). Per-id GETs hit the
    // DB, so the delta is arithmetically meaningful.
    const camerasAfterSeed = await countPresentCameras(h, session, SAMPLE_IDS);
    expect(camerasAfterSeed).toBeGreaterThanOrEqual(camerasBefore);
    const promised = /Created (\d+) cameras/.exec(toastText)?.[1];
    expect(promised).toBeDefined();
    expect(camerasAfterSeed - camerasBefore).toBe(Number(promised));

    // --- Seed Test Events: needs cameras first (admin.py:460 docstring), which
    // the leg above just guaranteed.
    await page.getByTestId('btn-seed-events').click();
    const eventDialog = page.getByTestId('confirm-dialog');
    await expect(eventDialog).toContainText('Seed Test Events');
    await eventDialog.getByRole('button', { name: 'Seed Events', exact: true }).click();
    const seedEventsToast = page
      .locator('[data-sonner-toast]')
      .filter({ hasText: /Created \d+ events/ });
    await expect(seedEventsToast).toBeVisible({ timeout: 20_000 });
    const eventsToastText = (await seedEventsToast.textContent()) ?? '';

    // The count the user was shown, pinned TWICE, because the loose version of
    // this check (`total > before`) passed while saying nothing about the 50 the
    // comment claimed. First pin: the number itself. 50 is the CLIENT's
    // constant, not the handler's — AdminSettings.tsx:396 sends `{ count: 50 }`
    // and the handler only loops `for _ in range(request.count)`
    // (backend/api/routes/admin.py:500), so a backend that stopped honouring
    // the request would contradict this pin. The F-162 precedent pins the same
    // toast at exactly 50 (test-data.spec.ts:146).
    const promisedEvents = /Created (\d+) events/.exec(eventsToastText)?.[1];
    expect(promisedEvents).toBeDefined();
    expect(Number(promisedEvents)).toBe(50);

    // Second pin: the toast's number is the number of rows the table gained —
    // the same "the toast must not lie" discipline as the cameras leg above.
    // Exact equality (not a `>` floor) is honest here only because nothing else
    // can insert Event rows in this boot: the events LIST is uncached (header),
    // the FileWatcher that auto-creates rows is off in CI
    // (docker-compose.ci.yml:139 `FILE_WATCHER_ENABLED=false`), and the seeded
    // `--fake` boot runs no VLM analysis, so the pipeline's own Event writer
    // (backend/services/vlm_analyzer.py:677) never fires.
    const eventsAfterSeed = (await api<EventList>(h, session, '/api/events?limit=1')).pagination
      ?.total;
    expect((eventsAfterSeed ?? 0) - (eventsBefore ?? 0)).toBe(Number(promisedEvents));

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

    // The wipe's camera leg is proved by the RESTORE LOOP below, not by a
    // per-id absence poll here, and the reason is deliberate: FileWatcher
    // auto-creates camera rows for directories (file_watcher.py:31,407 default
    // True) and the clear is DB-only — clear_seeded_data runs
    // delete(Event)/delete(Detection)/delete(Camera) (admin.py:714-716) then
    // commits (:761), leaving every folder on disk — so
    // "no rows right now" can race a resurrection and is not the invariant the
    // row promises. The precedent for this same reset (F-162,
    // test-data.spec.ts:235-253) proves camera absence the watcher-safe way:
    // create_camera answers 409 for an existing name (cameras.py:742-751) OR
    // folder_path (:753-764) and authPost throws on any non-2xx, so each
    // successful restore POST below is a positive proof the row was gone moments
    // earlier. Events (whose LIST is uncached) are polled to zero below.

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

    // The invariant the row promises: every harness camera the boot registered
    // is back, under the id the boot recorded. Counted per book id over
    // get_camera (a direct DB read) rather than as a list total, because the
    // POSTs above just changed the table and the camera list is cached
    // SHORT_TTL=60s on a key none of these handlers invalidate.
    const bookIds = Object.values(book);
    await expect
      .poll(() => countPresentCameras(h, session, bookIds), { timeout: 20_000 })
      .toBe(bookIds.length);
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
