/**
 * Uplevel F2.3 batch FE-4 — Camera Zone Editor & Zone Household Access
 * (`F-211`, `F-213`, `/settings/cameras`).
 *
 * Inventory rows covered:
 * - F-211: Cameras › Zone editor: draw, list, edit and delete zones (`/settings/cameras`,
 *          `GET /api/cameras/{camera_id}/zones`, `POST /api/cameras/{camera_id}/zones`,
 *          `PUT /api/cameras/{camera_id}/zones/{zone_id}`,
 *          `DELETE /api/cameras/{camera_id}/zones/{zone_id}`,
 *          `GET /api/cameras/{camera_id}/snapshot`)
 * - F-213: Cameras › Zone editor › Zone ownership / household access panel (`/settings/cameras`,
 *          `GET /api/zones/{zone_id}/household`, `PUT /api/zones/{zone_id}/household`,
 *          `PATCH /api/zones/{zone_id}/household`, `DELETE /api/zones/{zone_id}/household`,
 *          `GET /api/household/members`, `GET /api/household/vehicles`)
 *
 * Key implementation details verified against the tree:
 * - On the feature-check stack, `smoke()` (`scripts/feature_check.py:2082-2086`) drops an
 *   image into `harness-smoke`, so `GET /api/cameras/{harness_smoke_id}/snapshot`
 *   (`backend/api/routes/cameras.py:1215`) returns HTTP 200 and mounts the `<svg>` zone
 *   overlay inside `ZoneCanvas.tsx:383`.
 * - Drawing uses the Rectangle tool (`ZoneEditor.tsx:300-310`, `ZoneCanvas.tsx:144-210`)
 *   with a mouse drag across the `role="application"` drawing canvas (`ZoneCanvas.tsx:348-351`)
 *   so 4 distinct normalized vertices are produced (avoiding duplicate consecutive vertices on
 *   `dblclick` that `_has_duplicate_consecutive_points` in `backend/api/schemas/zone.py:143-144`
 *   rejects with 422).
 * - F-213 seeds two distinct household members (`ownerMember` and `allowedMember`) and one
 *   vehicle via `POST /api/household/members` and `POST /api/household/vehicles` so
 *   `data-testid="member-${id}"` and `data-testid="remove-member-${id}"` are strictly unique
 *   inside `zone-ownership-panel`, then cleans up all created fixtures in `finally`.
 */
import { expect, test } from '../guard';
import {
  apiPath,
  assertGuardSurvives,
  listCameras,
  readHarness,
  settledGoto,
  signIn,
  type AuthedFetch,
  type CameraRecord,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

async function pickSnapshotCamera(
  api: AuthedFetch,
  cameras: CameraRecord[]
): Promise<CameraRecord> {
  for (const cam of cameras) {
    const snapRes = await api.getJson(`/api/cameras/${cam.id}/snapshot`);
    if (snapRes.status === 200) {
      return cam;
    }
  }
  return cameras[0];
}

async function listZoneIds(api: AuthedFetch, cameraId: string): Promise<string[]> {
  const res = await api.getJson(`/api/cameras/${cameraId}/zones`);
  expect(res.status, `GET /api/cameras/${cameraId}/zones answers 200`).toBe(200);
  const items = Array.isArray(res.body?.items) ? res.body.items : [];
  return items.map((z: Record<string, unknown>) => String(z.id)).sort();
}

test.describe('FE-4 camera zones & zone household ownership golden path (F-211, F-213)', () => {
  test.setTimeout(120_000);

  test('F-211: Zone editor draws rectangle zone, lists it, updates it via PUT, and deletes it via DELETE', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const cameras = await listCameras(api);
    expect(cameras.length).toBeGreaterThan(0);
    const camera = await pickSnapshotCamera(api, cameras);
    const beforeZoneIds = await listZoneIds(api, camera.id);

    const runTag = Date.now().toString(36);
    const initialZoneName = `Golden FE4 Zone ${runTag}`;
    const updatedZoneName = `Golden FE4 Edited ${runTag}`;
    let createdZoneId: string | null = null;

    try {
      // 1. Navigate to /settings/cameras and open ZoneEditor modal (CamerasSettings.tsx:649-656)
      await settledGoto(page, h, '/settings/cameras', (p) =>
        p.getByRole('button', { name: `Configure zones for ${camera.name}` })
      );

      const zonesGetPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${camera.id}/zones` &&
          res.request().method() === 'GET'
      );
      await page.getByRole('button', { name: `Configure zones for ${camera.name}` }).click();
      await zonesGetPromise;

      await expect(page.getByText(`Zone Configuration - ${camera.name}`)).toBeVisible();
      const sidebar = page.getByTestId('zone-editor-sidebar');
      await expect(sidebar).toBeVisible();

      // 2. Click Rectangle tool and drag on the canvas (ZoneEditor.tsx:300-310, ZoneCanvas.tsx:348-351)
      await page.getByRole('button', { name: 'Rectangle' }).click();
      await expect(page.getByText('Drawing rectangle...')).toBeVisible();

      const drawCanvas = page.getByRole('application', {
        name: 'Zone drawing canvas - click and drag to draw',
      });
      await expect(drawCanvas).toBeVisible();
      const box = await drawCanvas.boundingBox();
      expect(box, 'drawing canvas has non-null bounding box').not.toBeNull();
      if (!box) throw new Error('drawing canvas boundingBox was null');

      const startX = box.x + box.width * 0.2;
      const startY = box.y + box.height * 0.2;
      const endX = box.x + box.width * 0.65;
      const endY = box.y + box.height * 0.65;

      await page.mouse.move(startX, startY);
      await page.mouse.down();
      await page.mouse.move(endX, endY, { steps: 5 });
      await page.mouse.up();

      // 3. Fill New Zone form (ZoneForm.tsx:167-316) and submit (POST /api/cameras/{id}/zones)
      await expect(page.getByText('New Zone')).toBeVisible();
      await page.getByLabel('Zone Name').fill(initialZoneName);
      await page.getByLabel('Zone Type').selectOption('entry_point');

      const createPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${camera.id}/zones` &&
          res.request().method() === 'POST'
      );
      await page.getByRole('button', { name: 'Create Zone' }).click();
      const createRes = await createPromise;
      expect(createRes.status(), 'POST /api/cameras/{id}/zones answers 201').toBe(201);
      const createdBody = await createRes.json();
      createdZoneId = String(createdBody.id);
      expect(createdZoneId.length).toBeGreaterThan(0);
      expect(createdBody.name).toBe(initialZoneName);
      expect(createdBody.zone_type).toBe('entry_point');
      expect(createdBody.shape).toBe('rectangle');
      expect(Array.isArray(createdBody.coordinates)).toBe(true);
      expect(createdBody.coordinates.length).toBe(4);

      // Verify zone appears in sidebar ZoneList (ZoneList.tsx:77-179) and backend GET
      await expect(sidebar.getByText(initialZoneName)).toBeVisible();
      await expect(sidebar.getByText('Entry Point')).toBeVisible();
      const afterCreateIds = await listZoneIds(api, camera.id);
      expect(afterCreateIds).toContain(createdZoneId);

      // 4. Edit the zone via ZoneForm (PUT /api/cameras/{id}/zones/{zone_id}, ZoneEditor.tsx:204)
      const zoneItem = sidebar
        .locator('[role="button"]')
        .filter({ hasText: initialZoneName })
        .first();
      await zoneItem.locator('button[title="Edit zone"]').click();

      await expect(page.getByText('Edit Zone')).toBeVisible();
      await page.getByLabel('Zone Name').fill(updatedZoneName);
      await page.getByLabel('Zone Type').selectOption('driveway');

      const updatePromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${camera.id}/zones/${createdZoneId}` &&
          res.request().method() === 'PUT'
      );
      await page.getByRole('button', { name: 'Update Zone' }).click();
      const updateRes = await updatePromise;
      expect(updateRes.status(), 'PUT /api/cameras/{id}/zones/{zone_id} answers 200').toBe(200);

      await expect(sidebar.getByText(updatedZoneName)).toBeVisible();
      await expect(sidebar.getByText('Driveway')).toBeVisible();

      const verifyEditRes = await api.getJson(`/api/cameras/${camera.id}/zones`);
      const editedZone = (verifyEditRes.body?.items ?? []).find(
        (z: Record<string, unknown>) => String(z.id) === createdZoneId
      );
      expect(editedZone?.name).toBe(updatedZoneName);
      expect(editedZone?.zone_type).toBe('driveway');

      // 5. Delete the zone and confirm (DELETE /api/cameras/{id}/zones/{zone_id}, ZoneEditor.tsx:245)
      const updatedZoneItem = sidebar
        .locator('[role="button"]')
        .filter({ hasText: updatedZoneName })
        .first();
      await updatedZoneItem.locator('button[title="Delete zone"]').click();

      await expect(
        page.getByText(`Delete zone "${updatedZoneName}"? This action cannot be undone.`)
      ).toBeVisible();

      const deletePromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/cameras/${camera.id}/zones/${createdZoneId}` &&
          res.request().method() === 'DELETE'
      );
      await page.getByRole('button', { name: 'Delete', exact: true }).click();
      const deleteRes = await deletePromise;
      expect(deleteRes.status(), 'DELETE /api/cameras/{id}/zones/{zone_id} answers 204').toBe(204);

      await expect(sidebar.getByText(updatedZoneName)).toHaveCount(0);
      const afterDeleteIds = await listZoneIds(api, camera.id);
      expect(afterDeleteIds).toEqual(beforeZoneIds);
      createdZoneId = null;

      await page.getByTestId('close-modal-btn').click();
      await assertGuardSurvives(page, h);
    } finally {
      if (createdZoneId) {
        const delRes = await api.send(`/api/cameras/${camera.id}/zones/${createdZoneId}`, 'DELETE');
        expect([204, 404]).toContain(delRes.status);
      }
      expect(await listZoneIds(api, camera.id)).toEqual(beforeZoneIds);
    }
  });

  test('F-213: Zone ownership panel configures owner, allowed members, and vehicles (GET/PUT/PATCH/DELETE /api/zones/{id}/household)', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    const cameras = await listCameras(api);
    expect(cameras.length).toBeGreaterThan(0);
    const camera = cameras[0];
    const beforeZoneIds = await listZoneIds(api, camera.id);

    const runTag = Date.now().toString(36);
    const zoneName = `Golden FE4 Access Zone ${runTag}`;
    const ownerName = `Golden Owner ${runTag}`;
    const allowedName = `Golden Allowed ${runTag}`;
    const vehicleDesc = `Golden Sedan ${runTag}`;

    let zoneId: string | null = null;
    let ownerMemberId: number | null = null;
    let allowedMemberId: number | null = null;
    let vehicleId: number | null = null;

    try {
      // 1. Seed a zone, two household members, and a registered vehicle via API
      const zoneRes = await api.send(`/api/cameras/${camera.id}/zones`, 'POST', {
        name: zoneName,
        zone_type: 'entry_point',
        coordinates: [
          [0.15, 0.15],
          [0.55, 0.15],
          [0.55, 0.55],
          [0.15, 0.55],
        ],
        shape: 'rectangle',
        color: '#3B82F6',
        enabled: true,
        priority: 10,
      });
      expect(zoneRes.status, 'seed zone created (201)').toBe(201);
      zoneId = String(zoneRes.body?.id);

      const ownerRes = await api.send('/api/household/members', 'POST', {
        name: ownerName,
        role: 'resident',
        trusted_level: 'full',
      });
      expect(ownerRes.status, 'owner household member created (201)').toBe(201);
      ownerMemberId = Number(ownerRes.body?.id);

      const allowedRes = await api.send('/api/household/members', 'POST', {
        name: allowedName,
        role: 'family',
        trusted_level: 'partial',
      });
      expect(allowedRes.status, 'allowed household member created (201)').toBe(201);
      allowedMemberId = Number(allowedRes.body?.id);

      const vehicleRes = await api.send('/api/household/vehicles', 'POST', {
        description: vehicleDesc,
        vehicle_type: 'car',
        trusted: true,
      });
      expect(vehicleRes.status, 'household vehicle created (201)').toBe(201);
      vehicleId = Number(vehicleRes.body?.id);

      // API-first check: GET /api/zones/{zone_id}/household returns 200 with null before config
      const initialHousehold = await api.getJson(`/api/zones/${zoneId}/household`);
      expect(initialHousehold.status).toBe(200);
      expect(initialHousehold.body).toBeNull();

      // 2. Open ZoneEditor on /settings/cameras, select the zone, switch to Configure tab
      await settledGoto(page, h, '/settings/cameras', (p) =>
        p.getByRole('button', { name: `Configure zones for ${camera.name}` })
      );
      await page.getByRole('button', { name: `Configure zones for ${camera.name}` }).click();

      const sidebar = page.getByTestId('zone-editor-sidebar');
      await expect(sidebar.getByText(zoneName)).toBeVisible();
      await sidebar.getByText(zoneName).click();
      await page.getByTestId('tab-configure').click();

      const panel = page.getByTestId('zone-ownership-panel');
      await expect(panel).toBeVisible();
      await expect(panel.getByTestId('empty-state')).toBeVisible();
      await expect(panel).toContainText('No ownership configured');

      // 3. Upsert ownership config via configure-modal (PUT /api/zones/{zone_id}/household)
      await panel.getByTestId('configure-btn').click();
      const configModal = page.getByTestId('configure-modal');
      await expect(configModal).toBeVisible();

      // Select owner in Tremor Select (ZoneOwnershipPanel.tsx:883-899); force:true bypasses
      // the nested Headless UI Dialog portal hit-target overlap over Tremor's Listbox.Options
      await configModal.getByTestId('owner-select').getByRole('button').click();
      await page.getByRole('option', { name: ownerName, exact: true }).click({ force: true });

      // Check allowed member and allowed vehicle checkboxes (ZoneOwnershipPanel.tsx:926, 964)
      await configModal.getByTestId(`member-checkbox-${allowedMemberId}`).check();
      await configModal.getByTestId(`vehicle-checkbox-${vehicleId}`).check();

      const putPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/zones/${zoneId}/household` &&
          res.request().method() === 'PUT'
      );
      await configModal.getByTestId('save-config-btn').click();
      const putRes = await putPromise;
      expect(putRes.status(), 'PUT /api/zones/{id}/household answers 200').toBe(200);

      // Verify backend persistence and UI cards
      const afterPut = await api.getJson(`/api/zones/${zoneId}/household`);
      expect(afterPut.status).toBe(200);
      expect(afterPut.body?.owner_id).toBe(ownerMemberId);
      expect(afterPut.body?.allowed_member_ids).toEqual([allowedMemberId]);
      expect(afterPut.body?.allowed_vehicle_ids).toEqual([vehicleId]);

      await expect(panel.getByTestId(`member-${ownerMemberId}`)).toBeVisible();
      await expect(panel.getByTestId(`member-${allowedMemberId}`)).toBeVisible();
      await expect(panel.getByTestId(`vehicle-${vehicleId}`)).toBeVisible();

      // 4. Inline remove vehicle triggers PATCH /api/zones/{zone_id}/household (ZoneOwnershipPanel.tsx:491-508)
      const patchPromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/zones/${zoneId}/household` &&
          res.request().method() === 'PATCH'
      );
      await panel.getByTestId(`remove-vehicle-${vehicleId}`).click({ force: true });
      const patchRes = await patchPromise;
      expect(patchRes.status(), 'PATCH /api/zones/{id}/household answers 200').toBe(200);

      await expect(panel.getByTestId(`vehicle-${vehicleId}`)).toHaveCount(0);
      await expect(panel).toContainText('No vehicles allowed');

      const afterPatch = await api.getJson(`/api/zones/${zoneId}/household`);
      expect(afterPatch.status).toBe(200);
      expect(afterPatch.body?.owner_id).toBe(ownerMemberId);
      expect(afterPatch.body?.allowed_member_ids).toEqual([allowedMemberId]);
      expect(afterPatch.body?.allowed_vehicle_ids).toEqual([]);

      // 5. Delete config via delete-config-btn (DELETE /api/zones/{zone_id}/household, :622-631, 980-991)
      await panel.getByTestId('edit-config-btn').click();
      await expect(configModal).toBeVisible();

      const deletePromise = page.waitForResponse(
        (res) =>
          apiPath(res.url()) === `/api/zones/${zoneId}/household` &&
          res.request().method() === 'DELETE'
      );
      await configModal.getByTestId('delete-config-btn').click();
      const deleteRes = await deletePromise;
      expect(deleteRes.status(), 'DELETE /api/zones/{id}/household answers 204').toBe(204);

      await expect(panel.getByTestId('empty-state')).toBeVisible();
      const afterDelete = await api.getJson(`/api/zones/${zoneId}/household`);
      expect(afterDelete.status).toBe(200);
      expect(afterDelete.body).toBeNull();

      await page.getByTestId('close-modal-btn').click();
      await assertGuardSurvives(page, h);
    } finally {
      if (zoneId) {
        await api.send(`/api/zones/${zoneId}/household`, 'DELETE');
        const delZone = await api.send(`/api/cameras/${camera.id}/zones/${zoneId}`, 'DELETE');
        expect([204, 404]).toContain(delZone.status);
      }
      if (vehicleId !== null) {
        const delVeh = await api.send(`/api/household/vehicles/${vehicleId}`, 'DELETE');
        expect([204, 404]).toContain(delVeh.status);
      }
      if (ownerMemberId !== null) {
        const delOwner = await api.send(`/api/household/members/${ownerMemberId}`, 'DELETE');
        expect([204, 404]).toContain(delOwner.status);
      }
      if (allowedMemberId !== null) {
        const delAllowed = await api.send(`/api/household/members/${allowedMemberId}`, 'DELETE');
        expect([204, 404]).toContain(delAllowed.status);
      }
      expect(await listZoneIds(api, camera.id)).toEqual(beforeZoneIds);
    }
  });
});
