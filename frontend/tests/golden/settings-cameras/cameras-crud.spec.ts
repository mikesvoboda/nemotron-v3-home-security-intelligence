/**
 * Uplevel F2.3 batch FE-4 — Cameras CRUD & Snapshot Cache TTL
 * (`F-199`, `F-200`, `F-201`, `F-203`, `/settings/cameras`).
 *
 * Inventory rows covered:
 * - F-199: Cameras › camera list and search (`/settings/cameras`, `GET /api/cameras`)
 * - F-200: Cameras › Add / Edit camera modal (`/settings/cameras`,
 *          `POST /api/cameras`, `PATCH /api/cameras/{camera_id}`)
 * - F-201: Cameras › Delete camera (`/settings/cameras`, `DELETE /api/cameras/{camera_id}`)
 * - F-203: Cameras › Snapshot cache TTL slider (`/settings/cameras`,
 *          `GET /api/v1/settings`, `PATCH /api/v1/settings`)
 *
 * Key code findings documented here:
 * - `useCamerasQuery` (`frontend/src/hooks/useCamerasQuery.ts:157-171`) configures
 *   `placeholderData: createPlaceholderCameras(6)`, which renders `placeholder-0`..`5`
 *   before `GET /api/cameras` resolves. Specs synchronize on real camera IDs from
 *   `GET /api/cameras` (`edit-camera-${cam.id}`) before asserting table rows.
 * - `CamerasSettings.tsx:268-278`: in Edit mode (`editingCamera !== null`), `handleSubmit`
 *   constructs `updateData` with `{ name, folder_path, status, motion_sensitivity? }`
 *   (omitting `ingestion_mode`, `rtsp_url`, `rtsp_username`, `rtsp_password`), whereas
 *   Add mode (`:281-300`) sends all RTSP/ONVIF fields in `POST /api/cameras`.
 * - `backend/api/schemas/camera.py:42-70` (`_validate_folder_path`) forbids `:` in
 *   `folder_path`, so `folder_path` must be a filesystem path (`/cameras/...`) while
 *   `rtsp_url` carries the `rtsp://...` URI.
 * - `CacheService.invalidate_cameras` (`backend/services/cache_service.py:577`) scans
 *   `"cache:cameras:*"` while `list_cameras` (`backend/api/routes/cameras.py:194, 259`)
 *   writes `CacheKeys.cameras_list_by_status(None)` (`"cache:hsi:cache:cameras:list:all"`,
 *   `SHORT_TTL = 60`s). Consequently, `_invalidate_cameras_cache_background` (`cameras.py:815,
 *   913, 992`) deletes `0` keys on create/update/delete, and `useCameraMutation.onSettled`
 *   (`useCamerasQuery.ts:364, 407, 439`) immediately refetches the stale 60s cached list from
 *   `GET /api/cameras`. F-200 and F-201 exercise the full modal UI + uncached `GET /api/cameras/{id}`
 *   verification while documenting and pinning that stale-list-cache behaviour.
 */
import { expect, test } from '../guard';
import {
  apiPath,
  assertGuardSurvivesCameras as assertGuardSurvives,
  deleteCameraIfPresent,
  formatSecondsAsHumanReadable,
  listCameras,
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

test.describe('FE-4 cameras CRUD & snapshot cache TTL golden path (F-199, F-200, F-201, F-203)', () => {
  test.setTimeout(120_000);

  test('F-199: camera list renders seeded cameras from GET /api/cameras and filters by search query', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/cameras (backend/api/routes/cameras.py:152-278)
    const cameras = await listCameras(api);
    expect(
      cameras.length,
      'feature_check seeds scenario cameras before golden runs'
    ).toBeGreaterThan(0);
    const targetCam = cameras[0];

    // 2. Navigate to /settings/cameras and wait for real camera rows (past placeholderData)
    await settledGoto(page, h, '/settings/cameras', (p) =>
      p.getByTestId(`edit-camera-${targetCam.id}`)
    );
    await expect(page.getByTestId('settings-cameras')).toBeVisible();

    // Verify every camera returned by GET /api/cameras is rendered with its controls
    for (const cam of cameras) {
      await expect(page.getByTestId(`edit-camera-${cam.id}`)).toBeVisible();
      await expect(page.getByTestId(`camera-status-indicator-${cam.id}`)).toBeVisible();
      await expect(page.getByTestId(`scene-change-${cam.id}`)).toBeVisible();
      await expect(page.getByTestId(`baseline-${cam.id}`)).toBeVisible();
      await expect(
        page.getByRole('button', { name: `Configure zones for ${cam.name}` })
      ).toBeVisible();
      await expect(page.getByRole('button', { name: `Delete ${cam.name}` })).toBeVisible();
    }

    // 3. Search filter (CamerasSettings.tsx:485-497)
    const searchInput = page.getByPlaceholder('Search cameras by name...');
    await expect(searchInput).toBeVisible();
    await searchInput.fill(targetCam.name);
    await expect(page.getByTestId(`edit-camera-${targetCam.id}`)).toBeVisible();
    for (const other of cameras.slice(1)) {
      if (!other.name.toLowerCase().includes(targetCam.name.toLowerCase())) {
        await expect(page.getByTestId(`edit-camera-${other.id}`)).toHaveCount(0);
      }
    }

    // 4. Empty search state + Clear Search button (CamerasSettings.tsx:516-529)
    const unmatchedQuery = '__no_such_camera_fe4_xyz__';
    await searchInput.fill(unmatchedQuery);
    await expect(page.getByRole('heading', { name: 'No cameras found' })).toBeVisible();
    await expect(
      page.getByText(`No cameras match "${unmatchedQuery}". Try a different search term.`)
    ).toBeVisible();
    const clearBtn = page.getByRole('button', { name: 'Clear Search' });
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();

    await expect(searchInput).toHaveValue('');
    await expect(page.getByTestId(`edit-camera-${targetCam.id}`)).toBeVisible();

    await assertGuardSurvives(page, h);
  });

  test('F-200: Add Camera modal creates an RTSP camera (POST /api/cameras) and Edit Camera modal updates it (PATCH /api/cameras/{id})', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const beforeCameras = await listCameras(api);
    expect(beforeCameras.length).toBeGreaterThan(0);
    const existingCam = beforeCameras[0];
    const existingDetailRes = await api.getJson(`/api/cameras/${existingCam.id}`);
    expect(existingDetailRes.status).toBe(200);
    const originalExisting = {
      name: String(existingDetailRes.body?.name ?? existingCam.name),
      folder_path: String(existingDetailRes.body?.folder_path ?? existingCam.folder_path),
      status: String(existingDetailRes.body?.status ?? existingCam.status),
      motion_sensitivity: Number(existingDetailRes.body?.motion_sensitivity ?? 0.5),
    };

    const runTag = Date.now().toString(36);
    const initialName = `Golden FE4 Add ${runTag}`;
    const initialFolder = `/cameras/golden_fe4_add_${runTag}`;
    const editedName = `${originalExisting.name} Edited`;
    const editedFolder = `${originalExisting.folder_path}_edited`;
    const editedStatus = originalExisting.status === 'online' ? 'offline' : 'online';
    let createdId: string | null = null;
    let editedExisting = false;

    try {
      await settledGoto(page, h, '/settings/cameras', (p) =>
        p.getByTestId(`edit-camera-${existingCam.id}`)
      );

      // --- Leg 1: Add Camera (POST /api/cameras, CamerasSettings.tsx:281-300) ---
      await page.getByRole('button', { name: 'Add Camera' }).first().click();
      await expect(page.getByTestId('camera-name-input')).toBeVisible();

      await page.getByTestId('camera-name-input').fill(initialName);
      await page.getByTestId('camera-folder-path-input').fill(initialFolder);
      await page.getByTestId('camera-status-select').selectOption('online');
      await page.getByTestId('camera-ingestion-mode-select').selectOption('rtsp');

      // RTSP-specific fields mount when ingestion_mode is 'rtsp' (CamerasSettings.tsx:950, 984, 1088)
      await expect(page.getByTestId('camera-rtsp-url-input')).toBeVisible();
      await page.getByTestId('camera-rtsp-url-input').fill('rtsp://127.0.0.1:8554/golden_fe4');
      await page.getByTestId('camera-rtsp-username-input').fill('golden_user');
      await page.getByTestId('camera-rtsp-password-input').fill('golden_pass');
      await expect(page.getByTestId('motion-sensitivity-slider')).toBeVisible();
      await expect(page.getByTestId('motion-sensitivity-value')).toHaveText('0.50');

      const postPromise = page.waitForResponse(
        (res) => apiPath(res.url()) === '/api/cameras' && res.request().method() === 'POST'
      );
      await page.getByTestId('save-settings').click();
      const postRes = await postPromise;
      expect(postRes.status(), 'POST /api/cameras answers 201').toBe(201);
      const createdBody = await postRes.json();
      createdId = String(createdBody.id);
      expect(createdId.length).toBeGreaterThan(0);

      // Verify backend persistence via direct GET /api/cameras/{id}
      const getCreated = await api.getJson(`/api/cameras/${createdId}`);
      expect(getCreated.status).toBe(200);
      expect(getCreated.body?.name).toBe(initialName);
      expect(getCreated.body?.folder_path).toBe(initialFolder);
      expect(getCreated.body?.status).toBe('online');
      expect(getCreated.body?.ingestion_mode).toBe('rtsp');
      expect(getCreated.body?.rtsp_url).toBe('rtsp://127.0.0.1:8554/golden_fe4');
      expect(getCreated.body?.rtsp_username).toBe('golden_user');
      expect(getCreated.body?.motion_sensitivity).toBe(0.5);

      // Add modal closes after save
      await expect(page.getByTestId('camera-name-input')).toHaveCount(0);

      // --- Leg 2: Edit Camera (PATCH /api/cameras/{id}, CamerasSettings.tsx:268-278) ---
      await page.getByTestId(`edit-camera-${existingCam.id}`).click();
      await expect(page.getByTestId('camera-name-input')).toHaveValue(originalExisting.name);
      await expect(page.getByTestId('camera-folder-path-input')).toHaveValue(
        originalExisting.folder_path
      );

      await page.getByTestId('camera-name-input').fill(editedName);
      await page.getByTestId('camera-folder-path-input').fill(editedFolder);
      await page.getByTestId('camera-status-select').selectOption(editedStatus);

      const patchPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${existingCam.id}` &&
          res.request().method() === 'PATCH'
      );
      await page.getByTestId('save-settings').click();
      const patchRes = await patchPromise;
      expect(patchRes.status(), 'PATCH /api/cameras/{id} answers 200').toBe(200);
      editedExisting = true;

      // Verify updated fields persisted in PostgreSQL via GET /api/cameras/{id}
      const getEdited = await api.getJson(`/api/cameras/${existingCam.id}`);
      expect(getEdited.status).toBe(200);
      expect(getEdited.body?.name).toBe(editedName);
      expect(getEdited.body?.folder_path).toBe(editedFolder);
      expect(getEdited.body?.status).toBe(editedStatus);

      await expect(page.getByTestId('camera-name-input')).toHaveCount(0);

      await assertGuardSurvives(page, h);
    } finally {
      if (editedExisting) {
        const restoreRes = await api.send(`/api/cameras/${existingCam.id}`, 'PATCH', {
          name: originalExisting.name,
          folder_path: originalExisting.folder_path,
          status: originalExisting.status,
          motion_sensitivity: originalExisting.motion_sensitivity,
        });
        expect(restoreRes.status, 'restore edited camera answers 200').toBe(200);
      }
      if (createdId) {
        await deleteCameraIfPresent(api, createdId);
      }
    }
  });

  test('F-201: Delete Camera modal enforces type-to-confirm and removes camera via DELETE /api/cameras/{id}', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. Pick a non-smoke camera already present in the cached camera list so the row is
    // immediately visible in the UI table, and snapshot its full record for restoration
    const cameras = await listCameras(api);
    expect(cameras.length).toBeGreaterThan(0);
    const targetCam =
      cameras.find((c) => c.id !== 'harness_smoke' && c.id !== 'front_door') ??
      cameras[cameras.length - 1];
    const detailRes = await api.getJson(`/api/cameras/${targetCam.id}`);
    expect(detailRes.status).toBe(200);
    const camName = String(detailRes.body?.name ?? targetCam.name);
    const camId = targetCam.id;
    let deleted = false;

    try {
      // 2. Navigate to /settings/cameras and wait for targetCam row
      await settledGoto(page, h, '/settings/cameras', (p) => p.getByTestId(`edit-camera-${camId}`));

      // 3. Open Delete Confirmation modal (CamerasSettings.tsx:662-668, 1162-1273)
      await page.getByRole('button', { name: `Delete ${camName}` }).click();

      const confirmInput = page.getByTestId('delete-confirm-input');
      const confirmBtn = page.getByTestId('confirm-delete-button');
      await expect(confirmInput).toBeVisible();
      await expect(confirmBtn).toBeDisabled();

      // Typing a non-matching name keeps confirm-delete-button disabled (CamerasSettings.tsx:166)
      await confirmInput.fill(`${camName}-wrong`);
      await expect(confirmBtn).toBeDisabled();

      // Typing the exact camera name enables confirm-delete-button
      await confirmInput.fill(camName);
      await expect(confirmBtn).toBeEnabled();

      const deletePromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${camId}` && res.request().method() === 'DELETE'
      );
      await confirmBtn.click();
      const deleteRes = await deletePromise;
      expect(deleteRes.status(), 'DELETE /api/cameras/{id} answers 204').toBe(204);
      deleted = true;

      // Direct backend verification: 404 on GET /api/cameras/{id}
      const afterGet = await api.getJson(`/api/cameras/${camId}`);
      expect(afterGet.status, 'deleted camera answers 404').toBe(404);

      // Modal unmounts after delete completes
      await expect(confirmInput).toHaveCount(0);

      await assertGuardSurvives(page, h);
    } finally {
      if (deleted) {
        // Recreate the camera with its original name & folder_path; normalize_camera_id(camName)
        // restores the exact same slug ID (cameras.py:748, test-data.spec.ts:183-188)
        const recreateRes = await api.send('/api/cameras', 'POST', {
          name: camName,
          folder_path: String(detailRes.body?.folder_path ?? targetCam.folder_path),
          status: String(detailRes.body?.status ?? targetCam.status ?? 'online'),
          ingestion_mode: String(detailRes.body?.ingestion_mode ?? 'ftp'),
        });
        expect([201, 409], 'recreate deleted camera answers 201').toContain(recreateRes.status);
        const restoredGet = await api.getJson(`/api/cameras/${camId}`);
        expect(restoredGet.status, 'restored camera is 200 in PostgreSQL').toBe(200);
      }
    }
  });

  test('F-203: Snapshot cache TTL slider mirrors GET /api/v1/settings and persists via PATCH /api/v1/settings', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // 1. API-first check: GET /api/v1/settings (backend/api/routes/settings_api.py:95-152)
    const beforeRes = await api.getJson('/api/v1/settings');
    expect(beforeRes.status, 'GET /api/v1/settings answers 200').toBe(200);
    const beforeTtl = Number(beforeRes.body?.camera?.snapshot_cache_ttl);
    expect(beforeTtl).toBeGreaterThanOrEqual(60);
    expect(beforeTtl).toBeLessThanOrEqual(86400);

    const targetTtl = beforeTtl >= 86400 ? beforeTtl - 60 : beforeTtl + 60;
    const stepKey = beforeTtl >= 86400 ? 'ArrowLeft' : 'ArrowRight';

    try {
      // 2. Navigate to /settings/cameras and wait for snapshot-cache-ttl-section
      await settledGoto(page, h, '/settings/cameras', (p) =>
        p.getByTestId('snapshot-cache-ttl-section')
      );

      const slider = page.getByTestId('snapshot-cache-ttl-slider');
      const valueReadout = page.getByTestId('snapshot-cache-ttl-value');
      await expect(slider).toHaveValue(String(beforeTtl));
      await expect(valueReadout).toHaveText(formatSecondsAsHumanReadable(beforeTtl));

      // 3. Step slider by 60s and await PATCH /api/v1/settings (CamerasSettings.tsx:453-457)
      const patchPromise = page.waitForResponse(
        (res) => apiPath(res.url()) === '/api/v1/settings' && res.request().method() === 'PATCH'
      );
      await slider.focus();
      await page.keyboard.press(stepKey);
      const patchRes = await patchPromise;
      expect(patchRes.status(), 'PATCH /api/v1/settings answers 200').toBe(200);

      // 4. Verify UI readout and backend persistence
      await expect(slider).toHaveValue(String(targetTtl));
      await expect(valueReadout).toHaveText(formatSecondsAsHumanReadable(targetTtl));

      const afterRes = await api.getJson('/api/v1/settings');
      expect(afterRes.status).toBe(200);
      expect(afterRes.body?.camera?.snapshot_cache_ttl).toBe(targetTtl);

      await assertGuardSurvives(page, h);
    } finally {
      const restoreRes = await api.send('/api/v1/settings', 'PATCH', {
        camera: { snapshot_cache_ttl: beforeTtl },
      });
      expect(restoreRes.status, 'restore camera.snapshot_cache_ttl answers 200').toBe(200);
      expect(restoreRes.body?.camera?.snapshot_cache_ttl).toBe(beforeTtl);
    }
  });
});
