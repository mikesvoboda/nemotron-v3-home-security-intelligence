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
 */
import { expect, test } from '../guard';
import {
  apiPath,
  assertGuardSurvives,
  deleteCameraIfPresent,
  formatSecondsAsHumanReadable,
  listCameras,
  readHarness,
  settledGoto,
  signIn,
  waitCameraAbsent,
  waitCameraPresent,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

test.describe('FE-4 cameras CRUD & snapshot cache TTL golden path (F-199, F-200, F-201, F-203)', () => {
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

    const runTag = Date.now().toString(36);
    const initialName = `Golden FE4 Add ${runTag}`;
    const initialFolder = `/cameras/golden_fe4_add_${runTag}`;
    const editedName = `Golden FE4 Edit ${runTag}`;
    const editedFolder = `/cameras/golden_fe4_edit_${runTag}`;
    let createdId: string | null = null;

    try {
      await settledGoto(page, h, '/settings/cameras', (p) =>
        p.getByTestId(`edit-camera-${beforeCameras[0].id}`)
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

      // Verify backend persistence via direct GET /api/cameras/{id} and list cache invalidation
      const getCreated = await api.getJson(`/api/cameras/${createdId}`);
      expect(getCreated.status).toBe(200);
      expect(getCreated.body?.name).toBe(initialName);
      expect(getCreated.body?.folder_path).toBe(initialFolder);
      expect(getCreated.body?.status).toBe('online');
      expect(getCreated.body?.ingestion_mode).toBe('rtsp');
      expect(getCreated.body?.rtsp_url).toBe('rtsp://127.0.0.1:8554/golden_fe4');
      expect(getCreated.body?.rtsp_username).toBe('golden_user');
      expect(getCreated.body?.motion_sensitivity).toBe(0.5);

      await waitCameraPresent(api, createdId);
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await expect(page.getByTestId(`edit-camera-${createdId}`)).toBeVisible();

      // --- Leg 2: Edit Camera (PATCH /api/cameras/{id}, CamerasSettings.tsx:268-278) ---
      await page.getByTestId(`edit-camera-${createdId}`).click();
      await expect(page.getByTestId('camera-name-input')).toHaveValue(initialName);
      await expect(page.getByTestId('camera-folder-path-input')).toHaveValue(initialFolder);

      await page.getByTestId('camera-name-input').fill(editedName);
      await page.getByTestId('camera-folder-path-input').fill(editedFolder);
      await page.getByTestId('camera-status-select').selectOption('offline');

      // Step motion-sensitivity-slider by +0.01 (0.50 -> 0.51)
      const sensitivitySlider = page.getByTestId('motion-sensitivity-slider');
      await sensitivitySlider.focus();
      await page.keyboard.press('ArrowRight');
      await expect(page.getByTestId('motion-sensitivity-value')).toHaveText('0.51');

      const patchPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${createdId}` && res.request().method() === 'PATCH'
      );
      await page.getByTestId('save-settings').click();
      const patchRes = await patchPromise;
      expect(patchRes.status(), 'PATCH /api/cameras/{id} answers 200').toBe(200);

      // Verify updated fields persisted on the backend and in the UI table
      const getEdited = await api.getJson(`/api/cameras/${createdId}`);
      expect(getEdited.status).toBe(200);
      expect(getEdited.body?.name).toBe(editedName);
      expect(getEdited.body?.folder_path).toBe(editedFolder);
      expect(getEdited.body?.status).toBe('offline');
      expect(getEdited.body?.motion_sensitivity).toBeCloseTo(0.51, 2);

      await expect
        .poll(
          async () => {
            const items = await listCameras(api);
            return items.find((c) => c.id === createdId)?.name;
          },
          { timeout: 10_000, intervals: [200, 400, 800] }
        )
        .toBe(editedName);
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));

      await expect(page.getByText(editedName)).toBeVisible();
      await expect(page.getByText(editedFolder)).toBeVisible();

      await assertGuardSurvives(page, h);
    } finally {
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

    // 1. Setup disposable camera via API so harness-seeded cameras are untouched
    const runTag = Date.now().toString(36);
    const camName = `Golden FE4 Delete ${runTag}`;
    const createRes = await api.send('/api/cameras', 'POST', {
      name: camName,
      folder_path: `/cameras/golden_fe4_delete_${runTag}`,
      status: 'online',
      ingestion_mode: 'ftp',
    });
    expect(createRes.status, 'disposable camera created (201)').toBe(201);
    const camId = String(createRes.body?.id);
    await waitCameraPresent(api, camId);

    try {
      // 2. Navigate to /settings/cameras and wait for the disposable camera row
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

      // Direct backend verification: 404 on GET /api/cameras/{id} and absent from list
      const afterGet = await api.getJson(`/api/cameras/${camId}`);
      expect(afterGet.status, 'deleted camera answers 404').toBe(404);
      await waitCameraAbsent(api, camId);
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));

      // Modal unmounts and row disappears from table
      await expect(confirmInput).toHaveCount(0);
      await expect(page.getByTestId(`edit-camera-${camId}`)).toHaveCount(0);

      await assertGuardSurvives(page, h);
    } finally {
      await deleteCameraIfPresent(api, camId);
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
